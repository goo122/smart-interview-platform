"""Persistence for image-free interview demeanor samples."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview.domain import InterviewDemeanorEvaluation, utc_now
from app.modules.interview.models import InterviewDemeanorEvaluationModel


class DemeanorEvaluationRepository(Protocol):
    async def create(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        overall_score: int,
        eye_contact_score: int,
        posture_score: int,
        facial_visibility_score: int,
        expression_naturalness_score: int,
        summary: str,
        suggestions: Sequence[str],
        confidence: int,
        provider_name: str,
        analysis_version: str,
        captured_at: datetime,
    ) -> InterviewDemeanorEvaluation: ...

    async def list_completed(
        self, session_id: UUID, user_id: UUID
    ) -> list[InterviewDemeanorEvaluation]: ...


class SqlAlchemyDemeanorEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        overall_score: int,
        eye_contact_score: int,
        posture_score: int,
        facial_visibility_score: int,
        expression_naturalness_score: int,
        summary: str,
        suggestions: Sequence[str],
        confidence: int,
        provider_name: str,
        analysis_version: str,
        captured_at: datetime,
    ) -> InterviewDemeanorEvaluation:
        now = utc_now()
        row = InterviewDemeanorEvaluationModel(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            overall_score=overall_score,
            eye_contact_score=eye_contact_score,
            posture_score=posture_score,
            facial_visibility_score=facial_visibility_score,
            expression_naturalness_score=expression_naturalness_score,
            summary=summary,
            suggestions=list(suggestions),
            confidence=confidence,
            provider_name=provider_name,
            analysis_version=analysis_version,
            captured_at=captured_at,
            created_at=now,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_domain(row)

    async def list_completed(
        self, session_id: UUID, user_id: UUID
    ) -> list[InterviewDemeanorEvaluation]:
        result = await self._session.execute(
            select(InterviewDemeanorEvaluationModel)
            .where(
                InterviewDemeanorEvaluationModel.session_id == session_id,
                InterviewDemeanorEvaluationModel.user_id == user_id,
            )
            .order_by(
                InterviewDemeanorEvaluationModel.captured_at.asc(),
                InterviewDemeanorEvaluationModel.id.asc(),
            )
        )
        return [_to_domain(row) for row in result.scalars().all()]


def _to_domain(row: InterviewDemeanorEvaluationModel) -> InterviewDemeanorEvaluation:
    return InterviewDemeanorEvaluation(
        id=row.id,
        session_id=row.session_id,
        user_id=row.user_id,
        overall_score=row.overall_score,
        eye_contact_score=row.eye_contact_score,
        posture_score=row.posture_score,
        facial_visibility_score=row.facial_visibility_score,
        expression_naturalness_score=row.expression_naturalness_score,
        summary=row.summary,
        suggestions=list(row.suggestions),
        confidence=row.confidence,
        provider_name=row.provider_name,
        analysis_version=row.analysis_version,
        captured_at=row.captured_at,
        created_at=row.created_at,
    )
