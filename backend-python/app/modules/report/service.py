import asyncio
import contextlib
from collections.abc import Iterable
from datetime import timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.ai.report import (
    InterviewReportNarrativePort,
    InterviewReportNarrativeRequest,
    RuleBasedInterviewReportNarrativeGenerator,
    StructuredInterviewReportNarrative,
)
from app.core.config import Settings
from app.modules.interview.domain import (
    InterviewEvaluation,
    InterviewSession,
    InterviewStatus,
    ResumeEvaluation,
    TurnStatus,
    utc_now,
)
from app.modules.interview.exceptions import InterviewNotFoundError
from app.modules.interview.repository import InterviewRepository
from app.modules.report.aggregation import (
    InterviewScoreAggregator,
    ReportAggregationWeights,
)
from app.modules.report.domain import (
    InterviewReport,
    InterviewReportDetail,
    InterviewReportItem,
    ReportGeneratedBy,
    ReportStatus,
    ReportTurnSnapshot,
)
from app.modules.report.exceptions import (
    ReportGenerationError,
    ReportLeaseLostError,
    ReportNotFoundError,
    ReportQueueUnavailableError,
    ReportSessionNotCompletedError,
    ReportWithoutCompletedAnswersError,
)
from app.modules.report.repository import InterviewReportRepository
from app.modules.report.snapshot import InterviewReportSnapshotBuilder
from app.workers.queue import InterviewReportGenerationJob, InterviewReportTaskQueuePort


class ReportGenerationRetryableError(RuntimeError):
    """Internal signal used by the ARQ worker to retry infrastructure failures."""

    def __init__(self, delay_seconds: float) -> None:
        super().__init__("Interview report generation will retry")
        self.delay_seconds = delay_seconds


class InterviewReportService:
    def __init__(
        self,
        interview_repository: InterviewRepository,
        report_repository: InterviewReportRepository,
        narrative: InterviewReportNarrativePort,
        task_queue: InterviewReportTaskQueuePort,
        settings: Settings,
    ) -> None:
        self._interview_repository = interview_repository
        self._report_repository = report_repository
        self._narrative = narrative
        self._task_queue = task_queue
        self._settings = settings
        self._aggregator = InterviewScoreAggregator(
            ReportAggregationWeights(
                primary_turn=settings.report_primary_turn_weight,
                follow_up_turn=settings.report_follow_up_turn_weight,
                technical=settings.report_technical_weight,
                relevance=settings.report_relevance_weight,
                clarity=settings.report_clarity_weight,
                depth=settings.report_depth_weight,
            )
        )
        self._snapshot_builder = InterviewReportSnapshotBuilder()

    async def generate(
        self, user_id: UUID, session_id: UUID, request_id: str | None = None
    ) -> InterviewReportDetail:
        session = await self._interview_repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        if session.status != InterviewStatus.COMPLETED:
            raise ReportSessionNotCompletedError(
                "Reports can only be generated for completed interviews"
            )
        turns = await self._interview_repository.list_turns(session_id, user_id)
        has_completed_answer = False
        for turn in turns:
            if turn.status != TurnStatus.COMPLETED:
                continue
            answer = await self._interview_repository.get_answer_for_turn(turn.id, user_id)
            evaluation = await self._interview_repository.get_evaluation_for_turn(
                turn.id, user_id
            )
            if answer is not None and evaluation is not None:
                has_completed_answer = True
                break
        if not has_completed_answer:
            raise ReportWithoutCompletedAnswersError(
                "至少完成并提交一道题后才能生成报告"
            )
        report = await self._report_repository.create_pending(session_id, user_id)
        if report.status == ReportStatus.FAILED:
            report = await self._report_repository.reset_for_retry(report.id, user_id)
        if report.status == ReportStatus.PENDING and report.generation_queued_at is None:
            job = InterviewReportGenerationJob(
                report_id=report.id,
                session_id=session_id,
                user_id=user_id,
                request_id=request_id or f"report:{report.id}",
            )
            try:
                await self._report_repository.mark_queued(report.id, user_id)
                await self._task_queue.enqueue_interview_report(job)
            except Exception as exc:
                with contextlib.suppress(Exception):
                    await self._report_repository.clear_queued(report.id, user_id)
                raise ReportQueueUnavailableError(
                    "Interview report is not available for generation right now"
                ) from exc
        return await self._get_detail_by_session(user_id, session_id)

    async def process_generation_job(
        self,
        job: InterviewReportGenerationJob,
        attempt: int,
        *,
        lease_repository: InterviewReportRepository | None = None,
    ) -> None:
        """Build and persist one report after an atomic, fenced PostgreSQL claim."""

        stale_before = utc_now() - timedelta(
            seconds=self._settings.report_generation_stale_seconds
        )
        claim = await self._report_repository.claim_generation(
            job.report_id,
            job.user_id,
            stale_before,
            self._settings.report_generation_lease_seconds,
            attempt,
            self._settings.report_task_max_attempts,
        )
        if claim is None:
            return
        fencing_token = claim.fencing_token
        renew_repository = lease_repository or self._report_repository
        lease_lost = asyncio.Event()
        renewal_task = asyncio.create_task(
            self._renew_generation_lease(
                renew_repository,
                job,
                fencing_token,
                lease_lost,
            ),
            name=f"report-lease-{job.report_id}",
        )
        try:
            await self._build_and_persist_report(job, fencing_token, lease_lost)
        except asyncio.CancelledError:
            await self._report_repository.release_generation_for_retry(
                job.report_id, job.user_id, fencing_token
            )
            raise
        except ReportLeaseLostError:
            return
        except ReportGenerationError as exc:
            await self._mark_failed_if_owner(job, fencing_token, exc.code.upper(), exc.message)
        except ValueError as exc:
            await self._mark_failed_if_owner(
                job,
                fencing_token,
                "REPORT_SNAPSHOT_INVALID",
                str(exc)[:2000],
            )
        except Exception as exc:
            if attempt >= self._settings.report_task_max_attempts:
                await self._mark_failed_if_owner(
                    job,
                    fencing_token,
                    "REPORT_GENERATION_RETRY_EXHAUSTED",
                    "Interview report generation failed after several attempts",
                )
                return
            released = await self._report_repository.release_generation_for_retry(
                job.report_id, job.user_id, fencing_token
            )
            if released:
                delay = self._settings.report_retry_base_seconds * (2 ** (attempt - 1))
                raise ReportGenerationRetryableError(delay) from exc
        finally:
            renewal_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await renewal_task

    async def _build_and_persist_report(
        self,
        job: InterviewReportGenerationJob,
        fencing_token: str,
        lease_lost: asyncio.Event,
    ) -> None:
        session = await self._interview_repository.get_for_user(job.session_id, job.user_id)
        if session is None or session.status != InterviewStatus.COMPLETED:
            raise ReportGenerationError("Interview session is no longer completed")
        turns = await self._interview_repository.list_turns(job.session_id, job.user_id)
        questions = await self._interview_repository.list_questions(job.session_id)
        answers: dict[UUID, str] = {}
        evaluations: dict[UUID, InterviewEvaluation] = {}
        for turn in turns:
            answer = await self._interview_repository.get_answer_for_turn(turn.id, job.user_id)
            evaluation = await self._interview_repository.get_evaluation_for_turn(
                turn.id, job.user_id
            )
            if answer is not None:
                answers[turn.id] = answer.content
            if evaluation is not None:
                evaluations[turn.id] = evaluation
        try:
            snapshots = self._snapshot_builder.build(
                session, turns, answers, evaluations, questions
            )
        except ValueError as exc:
            raise ReportGenerationError("Interview report snapshot is inconsistent") from exc
        scores = self._aggregator.aggregate(
            (snapshot.turn, snapshot.evaluation) for snapshot in snapshots
        )
        resume_evaluation = await self._load_resume_evaluation(job.session_id, job.user_id)
        resume_snapshot = _resume_evaluation_snapshot(resume_evaluation)
        if resume_evaluation is not None and resume_evaluation.overall_score is not None:
            scores = type(scores)(
                overall_score=scores.overall_score,
                technical_score=scores.technical_score,
                relevance_score=scores.relevance_score,
                clarity_score=scores.clarity_score,
                depth_score=scores.depth_score,
                radar_data=(
                    {"dimension": "resume", "score": resume_evaluation.overall_score},
                    *scores.radar_data,
                ),
            )
        strengths = _dedupe(
            item for snapshot in snapshots for item in snapshot.evaluation.strengths
        )
        weaknesses = _dedupe(
            item for snapshot in snapshots for item in snapshot.evaluation.weaknesses
        )
        improvements = _dedupe(
            item
            for snapshot in snapshots
            for item in snapshot.evaluation.suggested_improvements
        )
        request = InterviewReportNarrativeRequest(
            job_title=session.job_title,
            interview_type=session.interview_type.value,
            difficulty=session.difficulty.value,
            overall_score=scores.overall_score,
            technical_score=scores.technical_score,
            relevance_score=scores.relevance_score,
            clarity_score=scores.clarity_score,
            depth_score=scores.depth_score,
            strengths=tuple(strengths),
            weaknesses=tuple(weaknesses),
            suggested_improvements=tuple(improvements),
        )
        narrative, generated_by = await self._generate_narrative(request)
        if lease_lost.is_set():
            raise ReportLeaseLostError()
        items = tuple(_snapshot_to_item(job.report_id, snapshot) for snapshot in snapshots)
        try:
            await self._report_repository.persist_ready(
                job.report_id,
                job.user_id,
                scores=scores,
                strengths=strengths,
                weaknesses=weaknesses,
                suggested_improvements=improvements,
                summary=narrative.summary,
                action_plan=list(narrative.action_plan),
                recommended_level=narrative.recommended_level,
                aggregation_version=self._settings.report_aggregation_version,
                prompt_version=None,
                generated_by=generated_by,
                items=items,
                fencing_token=fencing_token,
                resume_evaluation_snapshot=resume_snapshot,
            )
        except RuntimeError as exc:
            if "lease lost" in str(exc):
                raise ReportLeaseLostError() from exc
            raise

    async def _mark_failed_if_owner(
        self,
        job: InterviewReportGenerationJob,
        fencing_token: str,
        failure_code: str,
        failure_message: str,
    ) -> None:
        try:
            await self._report_repository.mark_failed(
                job.report_id,
                job.user_id,
                failure_code,
                failure_message,
                fencing_token,
            )
        except RuntimeError as exc:
            if "lease lost" in str(exc):
                return
            raise

    async def _renew_generation_lease(
        self,
        repository: InterviewReportRepository,
        job: InterviewReportGenerationJob,
        fencing_token: str,
        lease_lost: asyncio.Event,
    ) -> None:
        interval = max(1.0, self._settings.report_generation_lease_seconds / 3)
        try:
            while True:
                await asyncio.sleep(interval)
                renewed = await repository.renew_generation_lease(
                    job.report_id,
                    job.user_id,
                    fencing_token,
                    self._settings.report_generation_lease_seconds,
                )
                if not renewed:
                    lease_lost.set()
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            lease_lost.set()

    async def get_by_session(self, user_id: UUID, session_id: UUID) -> InterviewReportDetail:
        session = await self._interview_repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        report = await self._report_repository.get_by_session(session_id, user_id)
        if report is None:
            raise ReportNotFoundError("Interview report not found")
        return await self._detail(report, user_id, session)

    async def get(self, user_id: UUID, report_id: UUID) -> InterviewReportDetail:
        report = await self._report_repository.get_for_user(report_id, user_id)
        if report is None:
            raise ReportNotFoundError("Interview report not found")
        session = await self._interview_repository.get_for_user(report.session_id, user_id)
        if session is None:
            raise ReportNotFoundError("Interview report not found")
        return await self._detail(report, user_id, session)

    async def list(
        self, user_id: UUID, current: int = 1, size: int = 10
    ) -> tuple[list[InterviewReportDetail], int]:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        reports, total = await self._report_repository.list_for_user(user_id, current, size)
        details: list[InterviewReportDetail] = []
        for report in reports:
            session = await self._interview_repository.get_for_user(report.session_id, user_id)
            if session is not None:
                details.append(await self._detail(report, user_id, session))
        return details, total

    async def _get_detail_by_session(
        self, user_id: UUID, session_id: UUID
    ) -> InterviewReportDetail:
        report = await self._report_repository.get_by_session(session_id, user_id)
        if report is None:
            raise ReportNotFoundError("Interview report not found")
        session = await self._interview_repository.get_for_user(session_id, user_id)
        if session is None:
            raise ReportNotFoundError("Interview session not found")
        return await self._detail(report, user_id, session)

    async def _detail(
        self, report: InterviewReport, user_id: UUID, session: InterviewSession
    ) -> InterviewReportDetail:
        items = await self._report_repository.list_items(report.id, user_id)
        return InterviewReportDetail(report=report, session=session, items=tuple(items))

    async def _generate_narrative(
        self, request: InterviewReportNarrativeRequest
    ) -> tuple[StructuredInterviewReportNarrative, ReportGeneratedBy]:
        for _attempt in range(2):
            try:
                result = await self._narrative.generate(request)
                return (
                    StructuredInterviewReportNarrative.model_validate(result),
                    ReportGeneratedBy.HYBRID,
                )
            except ValidationError as exc:
                del exc
            except Exception:
                break
        fallback = RuleBasedInterviewReportNarrativeGenerator()
        try:
            return await fallback.generate(request), ReportGeneratedBy.RULES
        except Exception as exc:
            raise ReportGenerationError(
                "Interview report narrative fallback failed"
            ) from exc

    async def _load_resume_evaluation(
        self, session_id: UUID, user_id: UUID
    ) -> ResumeEvaluation | None:
        getter = getattr(self._interview_repository, "get_resume_evaluation", None)
        if getter is None:
            return None
        return cast(ResumeEvaluation | None, await getter(session_id, user_id))


def _dedupe(values: Iterable[str], limit: int = 10) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def _resume_evaluation_snapshot(
    evaluation: ResumeEvaluation | None,
) -> dict[str, Any] | None:
    if evaluation is None:
        return None
    return {
        "status": evaluation.status.value,
        "overallScore": evaluation.overall_score,
        "skillsMatchScore": evaluation.skills_match_score,
        "experienceMatchScore": evaluation.experience_match_score,
        "evidenceQualityScore": evaluation.evidence_quality_score,
        "clarityScore": evaluation.clarity_score,
        "strengths": list(evaluation.strengths),
        "gaps": list(evaluation.gaps),
        "suggestions": list(evaluation.suggestions),
        "summary": evaluation.summary,
        "sourceDocumentIds": [str(value) for value in evaluation.source_document_ids],
        "evaluationVersion": evaluation.evaluation_version,
        "providerName": evaluation.provider_name,
        "failureCode": evaluation.failure_code,
        "evaluatedAt": evaluation.completed_at.isoformat()
        if evaluation.completed_at is not None
        else None,
    }


def _snapshot_to_item(
    report_id: UUID, snapshot: ReportTurnSnapshot
) -> InterviewReportItem:
    evaluation = snapshot.evaluation
    question = snapshot.question.content if snapshot.question else snapshot.turn.question_content
    sources = []
    if snapshot.question:
        sources = [
            {
                "fileName": citation.document_name,
                "sourceId": citation.source_id,
                "pageNumber": citation.page_number,
                "summary": citation.excerpt[:500],
            }
            for citation in snapshot.question.citations
        ]
    return InterviewReportItem(
        id=uuid4(),
        report_id=report_id,
        turn_id=snapshot.turn.id,
        parent_turn_id=snapshot.turn.parent_turn_id,
        sequence=snapshot.turn.sequence,
        turn_type=snapshot.turn.turn_type.value,
        question=question,
        answer=snapshot.answer,
        overall_score=evaluation.overall_score,
        technical_score=evaluation.technical_score,
        relevance_score=evaluation.relevance_score,
        clarity_score=evaluation.clarity_score,
        depth_score=evaluation.depth_score,
        strengths=list(evaluation.strengths),
        weaknesses=list(evaluation.weaknesses),
        feedback=evaluation.feedback,
        suggested_improvements=list(evaluation.suggested_improvements),
        sources=sources,
        created_at=evaluation.created_at,
    )
