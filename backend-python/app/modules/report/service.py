from collections.abc import Iterable
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.ai.report import (
    InterviewReportNarrativePort,
    InterviewReportNarrativeRequest,
    RuleBasedInterviewReportNarrativeGenerator,
    StructuredInterviewReportNarrative,
)
from app.core.config import Settings
from app.modules.interview.domain import InterviewEvaluation, InterviewSession, InterviewStatus
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
    ReportNotFoundError,
    ReportSessionNotCompletedError,
)
from app.modules.report.repository import InterviewReportRepository
from app.modules.report.snapshot import InterviewReportSnapshotBuilder
from app.workers.queue import TaskQueuePort


class InterviewReportService:
    def __init__(
        self,
        interview_repository: InterviewRepository,
        report_repository: InterviewReportRepository,
        narrative: InterviewReportNarrativePort,
        task_queue: TaskQueuePort,
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

    async def generate(self, user_id: UUID, session_id: UUID) -> InterviewReportDetail:
        session = await self._interview_repository.get_for_user(session_id, user_id)
        if session is None:
            raise InterviewNotFoundError("Interview session not found")
        if session.status != InterviewStatus.COMPLETED:
            raise ReportSessionNotCompletedError(
                "Reports can only be generated for completed interviews"
            )
        report = await self._report_repository.create_pending(session_id, user_id)
        if report.status != ReportStatus.READY:
            try:
                async def generate_task() -> None:
                    await self._generate_report(report.id, user_id, session_id)

                await self._task_queue.enqueue(generate_task)
            except Exception:
                await self._report_repository.mark_failed(
                    report.id,
                    user_id,
                    "REPORT_QUEUE_FAILED",
                    "Interview report could not be queued",
                )
        return await self._get_detail_by_session(user_id, session_id)

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

    async def _generate_report(
        self, report_id: UUID, user_id: UUID, session_id: UUID
    ) -> None:
        report, claimed = await self._report_repository.claim_generation(report_id, user_id)
        if not claimed:
            return
        try:
            session = await self._interview_repository.get_for_user(session_id, user_id)
            if session is None or session.status != InterviewStatus.COMPLETED:
                raise ReportGenerationError("Interview session is no longer completed")
            turns = await self._interview_repository.list_turns(session_id, user_id)
            questions = await self._interview_repository.list_questions(session_id)
            answers = {}
            evaluations: dict[UUID, InterviewEvaluation] = {}
            for turn in turns:
                answer = await self._interview_repository.get_answer_for_turn(turn.id, user_id)
                evaluation = await self._interview_repository.get_evaluation_for_turn(
                    turn.id, user_id
                )
                if answer is not None:
                    answers[turn.id] = answer.content
                if evaluation is not None:
                    evaluations[turn.id] = evaluation
            snapshots = self._snapshot_builder.build(
                session, turns, answers, evaluations, questions
            )
            scores = self._aggregator.aggregate(
                (snapshot.turn, snapshot.evaluation) for snapshot in snapshots
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
            items = tuple(_snapshot_to_item(report.id, snapshot) for snapshot in snapshots)
            await self._report_repository.persist_ready(
                report.id,
                user_id,
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
            )
        except ReportGenerationError as exc:
            await self._report_repository.mark_failed(
                report.id, user_id, exc.code.upper(), exc.message
            )
        except Exception:
            await self._report_repository.mark_failed(
                report.id,
                user_id,
                "REPORT_GENERATION_FAILED",
                "Interview report generation failed",
            )

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
        return await fallback.generate(request), ReportGeneratedBy.RULES


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
