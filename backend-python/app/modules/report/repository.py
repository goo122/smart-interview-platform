from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview.models import InterviewSessionModel
from app.modules.report.aggregation import AggregatedReportScores
from app.modules.report.domain import (
    InterviewReport,
    InterviewReportItem,
    ReportGeneratedBy,
    ReportGenerationClaim,
    ReportStatus,
)
from app.modules.report.models import InterviewReportItemModel, InterviewReportModel


class InterviewReportRepository(Protocol):
    async def create_pending(self, session_id: UUID, user_id: UUID) -> InterviewReport: ...

    async def mark_queued(self, report_id: UUID, user_id: UUID) -> InterviewReport: ...

    async def clear_queued(self, report_id: UUID, user_id: UUID) -> InterviewReport: ...

    async def reset_for_retry(self, report_id: UUID, user_id: UUID) -> InterviewReport: ...

    async def claim_generation(
        self,
        report_id: UUID,
        user_id: UUID,
        stale_before: datetime,
        lease_seconds: int,
        attempt: int,
        max_attempts: int,
    ) -> ReportGenerationClaim | None: ...

    async def renew_generation_lease(
        self, report_id: UUID, user_id: UUID, fencing_token: str, lease_seconds: int
    ) -> bool: ...

    async def release_generation_for_retry(
        self, report_id: UUID, user_id: UUID, fencing_token: str
    ) -> bool: ...

    async def list_recoverable_generations(
        self, stale_before: datetime, max_attempts: int, limit: int
    ) -> list[InterviewReport]: ...

    async def get_for_user(self, report_id: UUID, user_id: UUID) -> InterviewReport | None: ...

    async def get_by_session(
        self, session_id: UUID, user_id: UUID
    ) -> InterviewReport | None: ...

    async def list_for_user(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[InterviewReport], int]: ...

    async def list_items(self, report_id: UUID, user_id: UUID) -> list[InterviewReportItem]: ...

    async def persist_ready(
        self,
        report_id: UUID,
        user_id: UUID,
        *,
        scores: AggregatedReportScores,
        strengths: list[str],
        weaknesses: list[str],
        suggested_improvements: list[str],
        summary: str,
        action_plan: list[str],
        recommended_level: str | None,
        aggregation_version: str,
        prompt_version: str | None,
        generated_by: ReportGeneratedBy,
        items: Sequence[InterviewReportItem],
        fencing_token: str,
        resume_evaluation_snapshot: dict[str, Any] | None = None,
    ) -> InterviewReport: ...

    async def mark_failed(
        self,
        report_id: UUID,
        user_id: UUID,
        failure_code: str,
        failure_message: str,
        fencing_token: str,
    ) -> InterviewReport: ...


class SqlAlchemyInterviewReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(self, session_id: UUID, user_id: UUID) -> InterviewReport:
        existing = await self._session.scalar(
            select(InterviewReportModel).where(
                InterviewReportModel.session_id == session_id,
                InterviewReportModel.user_id == user_id,
            )
        )
        if existing is not None:
            return _report_to_domain(existing)
        now = _utc_now()
        row = InterviewReportModel(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            status=ReportStatus.PENDING.value,
            overall_score=0,
            technical_score=0,
            relevance_score=0,
            clarity_score=0,
            depth_score=0,
            radar_data=[],
            strengths=[],
            weaknesses=[],
            suggested_improvements=[],
            summary="",
            action_plan=[],
            recommended_level=None,
            aggregation_version="pending",
            prompt_version=None,
            generated_by=ReportGeneratedBy.RULES.value,
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
            generation_queued_at=None,
            generation_started_at=None,
            generation_completed_at=None,
            generation_attempt_count=0,
            generation_lease_expires_at=None,
            generation_fencing_token=None,
        )
        self._session.add(row)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            existing = await self._session.scalar(
                select(InterviewReportModel).where(
                    InterviewReportModel.session_id == session_id,
                    InterviewReportModel.user_id == user_id,
                )
            )
            if existing is None:
                raise exc
            return _report_to_domain(existing)
        await self._session.refresh(row)
        return _report_to_domain(row)

    async def mark_queued(self, report_id: UUID, user_id: UUID) -> InterviewReport:
        row = await self._locked_row(report_id, user_id)
        if row is None:
            raise ValueError("Interview report not found")
        if ReportStatus(row.status) == ReportStatus.READY:
            return _report_to_domain(row)
        if ReportStatus(row.status) == ReportStatus.FAILED:
            raise ValueError("Interview report is not pending")
        row.generation_queued_at = _utc_now()
        row.updated_at = _utc_now()
        await self._session.commit()
        await self._session.refresh(row)
        return _report_to_domain(row)

    async def clear_queued(self, report_id: UUID, user_id: UUID) -> InterviewReport:
        row = await self._locked_row(report_id, user_id)
        if row is None:
            raise ValueError("Interview report not found")
        if ReportStatus(row.status) == ReportStatus.PENDING:
            row.generation_queued_at = None
            row.updated_at = _utc_now()
            await self._session.commit()
            await self._session.refresh(row)
        return _report_to_domain(row)

    async def reset_for_retry(self, report_id: UUID, user_id: UUID) -> InterviewReport:
        row = await self._locked_row(report_id, user_id)
        if row is None:
            raise ValueError("Interview report not found")
        if ReportStatus(row.status) == ReportStatus.READY:
            return _report_to_domain(row)
        if ReportStatus(row.status) != ReportStatus.FAILED:
            return _report_to_domain(row)
        row.status = ReportStatus.PENDING.value
        row.generation_queued_at = None
        row.generation_started_at = None
        row.generation_completed_at = None
        row.generation_attempt_count = 0
        row.generation_lease_expires_at = None
        row.generation_fencing_token = None
        row.failure_code = None
        row.failure_message = None
        row.updated_at = _utc_now()
        await self._session.commit()
        await self._session.refresh(row)
        return _report_to_domain(row)

    async def claim_generation(
        self,
        report_id: UUID,
        user_id: UUID,
        stale_before: datetime,
        lease_seconds: int,
        attempt: int,
        max_attempts: int,
    ) -> ReportGenerationClaim | None:
        row = await self._locked_row(report_id, user_id)
        if row is None:
            raise ValueError("Interview report not found")
        status = ReportStatus(row.status)
        now = _utc_now()
        if status == ReportStatus.READY:
            return None
        if status == ReportStatus.GENERATING:
            lease_expired = row.generation_lease_expires_at is None or (
                row.generation_lease_expires_at <= now
            )
            if not lease_expired:
                return None
        elif status != ReportStatus.PENDING:
            return None
        next_attempt = max(attempt, row.generation_attempt_count + 1)
        if next_attempt > max_attempts:
            return None
        token = uuid4().hex
        row.status = ReportStatus.GENERATING.value
        row.failure_code = None
        row.failure_message = None
        row.generation_attempt_count = next_attempt
        row.generation_started_at = now
        row.generation_lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.generation_fencing_token = token
        row.updated_at = now
        await self._session.commit()
        await self._session.refresh(row)
        return ReportGenerationClaim(_report_to_domain(row), token)

    async def renew_generation_lease(
        self, report_id: UUID, user_id: UUID, fencing_token: str, lease_seconds: int
    ) -> bool:
        row = await self._locked_row(report_id, user_id)
        if row is None or row.status != ReportStatus.GENERATING.value:
            return False
        if row.generation_fencing_token != fencing_token:
            return False
        now = _utc_now()
        row.generation_lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.updated_at = now
        await self._session.commit()
        return True

    async def release_generation_for_retry(
        self, report_id: UUID, user_id: UUID, fencing_token: str
    ) -> bool:
        row = await self._locked_row(report_id, user_id)
        if row is None or row.status != ReportStatus.GENERATING.value:
            return False
        if row.generation_fencing_token != fencing_token:
            return False
        row.status = ReportStatus.PENDING.value
        row.generation_queued_at = None
        row.generation_lease_expires_at = None
        row.generation_fencing_token = None
        row.updated_at = _utc_now()
        await self._session.commit()
        return True

    async def list_recoverable_generations(
        self, stale_before: datetime, max_attempts: int, limit: int
    ) -> list[InterviewReport]:
        now = _utc_now()
        result = await self._session.execute(
            select(InterviewReportModel)
            .join(
                InterviewSessionModel,
                InterviewSessionModel.id == InterviewReportModel.session_id,
            )
            .where(
                InterviewSessionModel.status == "COMPLETED",
                InterviewReportModel.generation_attempt_count < max_attempts,
                (
                    (InterviewReportModel.status == ReportStatus.PENDING.value)
                    & (
                        (InterviewReportModel.generation_queued_at.is_(None))
                        | (InterviewReportModel.generation_queued_at <= stale_before)
                    )
                )
                | (
                    (InterviewReportModel.status == ReportStatus.GENERATING.value)
                    & (
                        InterviewReportModel.generation_lease_expires_at.is_(None)
                        | (InterviewReportModel.generation_lease_expires_at <= now)
                    )
                ),
            )
            .order_by(InterviewReportModel.updated_at.asc())
            .limit(limit)
        )
        return [_report_to_domain(row) for row in result.scalars().all()]

    async def get_for_user(self, report_id: UUID, user_id: UUID) -> InterviewReport | None:
        row = await self._session.scalar(
            select(InterviewReportModel).where(
                InterviewReportModel.id == report_id,
                InterviewReportModel.user_id == user_id,
            )
        )
        return _report_to_domain(row) if row is not None else None

    async def get_by_session(
        self, session_id: UUID, user_id: UUID
    ) -> InterviewReport | None:
        row = await self._session.scalar(
            select(InterviewReportModel).where(
                InterviewReportModel.session_id == session_id,
                InterviewReportModel.user_id == user_id,
            )
        )
        return _report_to_domain(row) if row is not None else None

    async def list_for_user(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[InterviewReport], int]:
        query = select(InterviewReportModel).where(InterviewReportModel.user_id == user_id)
        count = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        result = await self._session.execute(
            query.order_by(InterviewReportModel.updated_at.desc())
            .offset((current - 1) * size)
            .limit(size)
        )
        return [_report_to_domain(row) for row in result.scalars().all()], int(count or 0)

    async def list_items(self, report_id: UUID, user_id: UUID) -> list[InterviewReportItem]:
        result = await self._session.execute(
            select(InterviewReportItemModel)
            .join(
                InterviewReportModel,
                InterviewReportModel.id == InterviewReportItemModel.report_id,
            )
            .where(
                InterviewReportItemModel.report_id == report_id,
                InterviewReportModel.user_id == user_id,
            )
            .order_by(InterviewReportItemModel.sequence.asc())
        )
        return [_item_to_domain(row) for row in result.scalars().all()]

    async def persist_ready(
        self,
        report_id: UUID,
        user_id: UUID,
        *,
        scores: AggregatedReportScores,
        strengths: list[str],
        weaknesses: list[str],
        suggested_improvements: list[str],
        summary: str,
        action_plan: list[str],
        recommended_level: str | None,
        aggregation_version: str,
        prompt_version: str | None,
        generated_by: ReportGeneratedBy,
        items: Sequence[InterviewReportItem],
        fencing_token: str,
        resume_evaluation_snapshot: dict[str, Any] | None = None,
    ) -> InterviewReport:
        row = await self._locked_row(report_id, user_id)
        if row is None:
            raise ValueError("Interview report not found")
        if ReportStatus(row.status) == ReportStatus.READY:
            return _report_to_domain(row)
        if ReportStatus(row.status) != ReportStatus.GENERATING:
            raise ValueError("Interview report is not generating")
        if row.generation_fencing_token != fencing_token:
            raise RuntimeError("Interview report generation lease lost")
        await self._session.execute(
            delete(InterviewReportItemModel).where(
                InterviewReportItemModel.report_id == report_id
            )
        )
        for item in items:
            self._session.add(
                InterviewReportItemModel(
                    id=item.id,
                    report_id=report_id,
                    turn_id=item.turn_id,
                    parent_turn_id=item.parent_turn_id,
                    sequence=item.sequence,
                    turn_type=item.turn_type,
                    question=item.question,
                    answer=item.answer,
                    overall_score=item.overall_score,
                    technical_score=item.technical_score,
                    relevance_score=item.relevance_score,
                    clarity_score=item.clarity_score,
                    depth_score=item.depth_score,
                    strengths=item.strengths,
                    weaknesses=item.weaknesses,
                    feedback=item.feedback,
                    suggested_improvements=item.suggested_improvements,
                    sources=item.sources,
                    created_at=item.created_at,
                )
            )
        now = _utc_now()
        row.status = ReportStatus.READY.value
        row.overall_score = scores.overall_score
        row.technical_score = scores.technical_score
        row.relevance_score = scores.relevance_score
        row.clarity_score = scores.clarity_score
        row.depth_score = scores.depth_score
        row.radar_data = list(scores.radar_data)
        row.strengths = strengths
        row.weaknesses = weaknesses
        row.suggested_improvements = suggested_improvements
        row.summary = summary
        row.action_plan = action_plan
        row.recommended_level = recommended_level
        row.aggregation_version = aggregation_version
        row.prompt_version = prompt_version
        row.generated_by = generated_by.value
        row.resume_evaluation_snapshot = resume_evaluation_snapshot
        row.failure_code = None
        row.failure_message = None
        row.updated_at = now
        row.completed_at = now
        row.generation_completed_at = now
        row.generation_lease_expires_at = None
        row.generation_fencing_token = None
        await self._session.commit()
        await self._session.refresh(row)
        return _report_to_domain(row)

    async def mark_failed(
        self,
        report_id: UUID,
        user_id: UUID,
        failure_code: str,
        failure_message: str,
        fencing_token: str,
    ) -> InterviewReport:
        await self._session.rollback()
        row = await self._locked_row(report_id, user_id)
        if row is None:
            raise ValueError("Interview report not found")
        if ReportStatus(row.status) == ReportStatus.READY:
            return _report_to_domain(row)
        if row.generation_fencing_token != fencing_token:
            raise RuntimeError("Interview report generation lease lost")
        await self._session.execute(
            delete(InterviewReportItemModel).where(
                InterviewReportItemModel.report_id == report_id
            )
        )
        row.status = ReportStatus.FAILED.value
        row.failure_code = failure_code[:64]
        row.failure_message = failure_message[:2000]
        row.updated_at = _utc_now()
        row.completed_at = None
        row.generation_lease_expires_at = None
        row.generation_fencing_token = None
        await self._session.commit()
        await self._session.refresh(row)
        return _report_to_domain(row)

    async def _locked_row(self, report_id: UUID, user_id: UUID) -> InterviewReportModel | None:
        result = await self._session.execute(
            select(InterviewReportModel)
            .where(
                InterviewReportModel.id == report_id,
                InterviewReportModel.user_id == user_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _report_to_domain(row: InterviewReportModel) -> InterviewReport:
    return InterviewReport(
        id=row.id,
        session_id=row.session_id,
        user_id=row.user_id,
        status=ReportStatus(row.status),
        overall_score=row.overall_score,
        technical_score=row.technical_score,
        relevance_score=row.relevance_score,
        clarity_score=row.clarity_score,
        depth_score=row.depth_score,
        radar_data=list(row.radar_data),
        strengths=list(row.strengths),
        weaknesses=list(row.weaknesses),
        suggested_improvements=list(row.suggested_improvements),
        summary=row.summary,
        action_plan=list(row.action_plan),
        recommended_level=row.recommended_level,
        aggregation_version=row.aggregation_version,
        prompt_version=row.prompt_version,
        generated_by=ReportGeneratedBy(row.generated_by),
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        resume_evaluation_snapshot=(
            dict(row.resume_evaluation_snapshot)
            if row.resume_evaluation_snapshot is not None
            else None
        ),
        generation_queued_at=row.generation_queued_at,
        generation_started_at=row.generation_started_at,
        generation_completed_at=row.generation_completed_at,
        generation_attempt_count=row.generation_attempt_count,
        generation_lease_expires_at=row.generation_lease_expires_at,
        generation_fencing_token=row.generation_fencing_token,
    )


def _item_to_domain(row: InterviewReportItemModel) -> InterviewReportItem:
    return InterviewReportItem(
        id=row.id,
        report_id=row.report_id,
        turn_id=row.turn_id,
        parent_turn_id=row.parent_turn_id,
        sequence=row.sequence,
        turn_type=row.turn_type,
        question=row.question,
        answer=row.answer,
        overall_score=row.overall_score,
        technical_score=row.technical_score,
        relevance_score=row.relevance_score,
        clarity_score=row.clarity_score,
        depth_score=row.depth_score,
        strengths=list(row.strengths),
        weaknesses=list(row.weaknesses),
        feedback=row.feedback,
        suggested_improvements=list(row.suggested_improvements),
        sources=list(row.sources),
        created_at=row.created_at,
    )
