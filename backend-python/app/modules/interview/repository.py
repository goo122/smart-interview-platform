from collections.abc import Sequence
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewEvent,
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    utc_now,
)
from app.modules.interview.exceptions import (
    InterviewNotFoundError,
    InterviewRequestAlreadyExistsError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.models import (
    InterviewEventModel,
    InterviewQuestionCitationModel,
    InterviewQuestionModel,
    InterviewSessionModel,
)
from app.modules.interview.state_machine import InterviewStateMachine


class InterviewRepository(Protocol):
    async def create(self, session: InterviewSession) -> InterviewSession: ...

    async def find_by_request(self, user_id: UUID, request_id: str) -> InterviewSession | None: ...

    async def get_for_user(self, session_id: UUID, user_id: UUID) -> InterviewSession | None: ...

    async def list_for_user(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[InterviewSession], int]: ...

    async def begin_preparing(
        self, session_id: UUID, user_id: UUID
    ) -> tuple[InterviewSession, bool]: ...

    async def persist_questions_and_ready(
        self, session_id: UUID, user_id: UUID, questions: Sequence[InterviewQuestion]
    ) -> InterviewSession: ...

    async def mark_failed(
        self, session_id: UUID, user_id: UUID, failure_code: str, failure_message: str
    ) -> InterviewSession: ...

    async def start(self, session_id: UUID, user_id: UUID) -> InterviewSession: ...

    async def cancel(self, session_id: UUID, user_id: UUID) -> InterviewSession: ...

    async def list_questions(self, session_id: UUID) -> list[InterviewQuestion]: ...

    async def list_events(self, session_id: UUID) -> list[InterviewEvent]: ...


class SqlAlchemyInterviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._state_machine = InterviewStateMachine()

    async def create(self, session: InterviewSession) -> InterviewSession:
        row = InterviewSessionModel(
            id=session.id,
            user_id=session.user_id,
            knowledge_base_id=session.knowledge_base_id,
            job_title=session.job_title,
            job_description=session.job_description,
            interview_type=session.interview_type.value,
            difficulty=session.difficulty.value,
            question_count=session.question_count,
            status=session.status.value,
            current_question_index=session.current_question_index,
            version=session.version,
            request_id=session.request_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        self._session.add(
            _event_row(
                session.id,
                "SESSION_CREATED",
                None,
                InterviewStatus.CREATED,
                {"request_id_present": session.request_id is not None},
                session.request_id,
            )
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise InterviewRequestAlreadyExistsError("Interview request already exists") from exc
        await self._session.refresh(row)
        return _session_to_domain(row)

    async def find_by_request(self, user_id: UUID, request_id: str) -> InterviewSession | None:
        result = await self._session.execute(
            select(InterviewSessionModel).where(
                InterviewSessionModel.user_id == user_id,
                InterviewSessionModel.request_id == request_id,
            )
        )
        row = result.scalar_one_or_none()
        return _session_to_domain(row) if row is not None else None

    async def get_for_user(self, session_id: UUID, user_id: UUID) -> InterviewSession | None:
        result = await self._session.execute(
            select(InterviewSessionModel).where(
                InterviewSessionModel.id == session_id,
                InterviewSessionModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _session_to_domain(row) if row is not None else None

    async def list_for_user(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[InterviewSession], int]:
        query = select(InterviewSessionModel).where(InterviewSessionModel.user_id == user_id)
        count = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        result = await self._session.execute(
            query.order_by(InterviewSessionModel.updated_at.desc())
            .offset((current - 1) * size)
            .limit(size)
        )
        return [_session_to_domain(row) for row in result.scalars().all()], int(count or 0)

    async def begin_preparing(
        self, session_id: UUID, user_id: UUID
    ) -> tuple[InterviewSession, bool]:
        row = await self._locked_row(session_id, user_id)
        if row is None:
            raise InterviewNotFoundError("Interview session not found")
        current = InterviewStatus(row.status)
        if current == InterviewStatus.PREPARING:
            return _session_to_domain(row), False
        if current != InterviewStatus.CREATED:
            if current in {
                InterviewStatus.READY,
                InterviewStatus.FAILED,
                InterviewStatus.CANCELLED,
            }:
                return _session_to_domain(row), False
            raise InvalidInterviewTransitionError(
                f"Cannot prepare interview from {current.value}"
            )
        self._state_machine.transition(current, InterviewStatus.PREPARING)
        now = utc_now()
        row.status = InterviewStatus.PREPARING.value
        row.version += 1
        row.updated_at = now
        self._session.add(
            _event_row(
                row.id,
                "STATUS_CHANGED",
                current,
                InterviewStatus.PREPARING,
                {"version": row.version},
                row.request_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(row)
        return _session_to_domain(row), True

    async def persist_questions_and_ready(
        self, session_id: UUID, user_id: UUID, questions: Sequence[InterviewQuestion]
    ) -> InterviewSession:
        row = await self._locked_row(session_id, user_id)
        if row is None:
            raise InterviewNotFoundError("Interview session not found")
        current = InterviewStatus(row.status)
        if current == InterviewStatus.READY:
            return _session_to_domain(row)
        self._state_machine.transition(current, InterviewStatus.READY)
        await self._session.execute(
            delete(InterviewQuestionModel).where(InterviewQuestionModel.session_id == session_id)
        )
        for question in questions:
            self._session.add(
                InterviewQuestionModel(
                    id=question.id,
                    session_id=question.session_id,
                    sequence=question.sequence,
                    content=question.content,
                    category=question.category,
                    difficulty=question.difficulty.value,
                    expected_points=question.expected_points,
                    source_summary=question.source_summary,
                    created_at=question.created_at,
                )
            )
        await self._session.flush()
        for question in questions:
            self._session.add_all(
                InterviewQuestionCitationModel(
                    id=citation.id,
                    question_id=question.id,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    source_id=citation.source_id,
                    page_number=citation.page_number,
                    score=citation.score,
                    excerpt=citation.excerpt,
                    ordinal=citation.ordinal,
                    created_at=citation.created_at,
                )
                for citation in question.citations
            )
        now = utc_now()
        row.status = InterviewStatus.READY.value
        row.prepared_at = now
        row.updated_at = now
        row.version += 1
        self._session.add(
            _event_row(
                row.id,
                "STATUS_CHANGED",
                current,
                InterviewStatus.READY,
                {"question_count": len(questions), "version": row.version},
                row.request_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(row)
        return _session_to_domain(row)

    async def mark_failed(
        self, session_id: UUID, user_id: UUID, failure_code: str, failure_message: str
    ) -> InterviewSession:
        row = await self._locked_row(session_id, user_id)
        if row is None:
            raise InterviewNotFoundError("Interview session not found")
        current = InterviewStatus(row.status)
        if current == InterviewStatus.FAILED:
            return _session_to_domain(row)
        if current == InterviewStatus.CANCELLED:
            return _session_to_domain(row)
        if current not in {InterviewStatus.CREATED, InterviewStatus.PREPARING}:
            raise InvalidInterviewTransitionError(f"Cannot fail interview from {current.value}")
        await self._session.execute(
            delete(InterviewQuestionModel).where(InterviewQuestionModel.session_id == session_id)
        )
        now = utc_now()
        row.status = InterviewStatus.FAILED.value
        row.failure_code = failure_code[:64]
        row.failure_message = failure_message[:2000]
        row.updated_at = now
        row.version += 1
        self._session.add(
            _event_row(
                row.id,
                "STATUS_CHANGED",
                current,
                InterviewStatus.FAILED,
                {"failure_code": row.failure_code, "version": row.version},
                row.request_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(row)
        return _session_to_domain(row)

    async def start(self, session_id: UUID, user_id: UUID) -> InterviewSession:
        row = await self._locked_row(session_id, user_id)
        if row is None:
            raise InterviewNotFoundError("Interview session not found")
        current = InterviewStatus(row.status)
        if current == InterviewStatus.IN_PROGRESS:
            return _session_to_domain(row)
        self._state_machine.transition(current, InterviewStatus.IN_PROGRESS)
        now = utc_now()
        row.status = InterviewStatus.IN_PROGRESS.value
        row.started_at = now
        row.updated_at = now
        row.version += 1
        self._session.add(
            _event_row(
                row.id,
                "STATUS_CHANGED",
                current,
                InterviewStatus.IN_PROGRESS,
                {"version": row.version},
                row.request_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(row)
        return _session_to_domain(row)

    async def cancel(self, session_id: UUID, user_id: UUID) -> InterviewSession:
        row = await self._locked_row(session_id, user_id)
        if row is None:
            raise InterviewNotFoundError("Interview session not found")
        current = InterviewStatus(row.status)
        if current == InterviewStatus.CANCELLED:
            return _session_to_domain(row)
        self._state_machine.transition(current, InterviewStatus.CANCELLED)
        now = utc_now()
        row.status = InterviewStatus.CANCELLED.value
        row.updated_at = now
        row.finished_at = now
        row.version += 1
        self._session.add(
            _event_row(
                row.id,
                "STATUS_CHANGED",
                current,
                InterviewStatus.CANCELLED,
                {"version": row.version},
                row.request_id,
            )
        )
        await self._session.commit()
        await self._session.refresh(row)
        return _session_to_domain(row)

    async def list_questions(self, session_id: UUID) -> list[InterviewQuestion]:
        result = await self._session.execute(
            select(InterviewQuestionModel)
            .where(InterviewQuestionModel.session_id == session_id)
            .order_by(InterviewQuestionModel.sequence.asc())
        )
        rows = result.scalars().all()
        if not rows:
            return []
        citation_result = await self._session.execute(
            select(InterviewQuestionCitationModel)
            .where(InterviewQuestionCitationModel.question_id.in_([row.id for row in rows]))
            .order_by(
                InterviewQuestionCitationModel.question_id,
                InterviewQuestionCitationModel.ordinal,
            )
        )
        by_question: dict[UUID, list[InterviewQuestionCitation]] = {}
        for citation in citation_result.scalars().all():
            by_question.setdefault(citation.question_id, []).append(_citation_to_domain(citation))
        return [
            _question_to_domain(row, by_question.get(row.id, []))
            for row in rows
        ]

    async def list_events(self, session_id: UUID) -> list[InterviewEvent]:
        result = await self._session.execute(
            select(InterviewEventModel)
            .where(InterviewEventModel.session_id == session_id)
            .order_by(InterviewEventModel.created_at.asc())
        )
        return [_event_to_domain(row) for row in result.scalars().all()]

    async def _locked_row(self, session_id: UUID, user_id: UUID) -> InterviewSessionModel | None:
        result = await self._session.execute(
            select(InterviewSessionModel)
            .where(
                InterviewSessionModel.id == session_id,
                InterviewSessionModel.user_id == user_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()


def _event_row(
    session_id: UUID,
    event_type: str,
    from_status: InterviewStatus | None,
    to_status: InterviewStatus,
    payload: dict[str, object],
    idempotency_key: str | None,
) -> InterviewEventModel:
    return InterviewEventModel(
        id=uuid4(),
        session_id=session_id,
        event_type=event_type,
        from_status=from_status.value if from_status else None,
        to_status=to_status.value,
        payload=payload,
        idempotency_key=idempotency_key,
        created_at=utc_now(),
    )


def _session_to_domain(row: InterviewSessionModel) -> InterviewSession:
    return InterviewSession(
        id=row.id,
        user_id=row.user_id,
        knowledge_base_id=row.knowledge_base_id,
        job_title=row.job_title,
        job_description=row.job_description,
        interview_type=InterviewType(row.interview_type),
        difficulty=InterviewDifficulty(row.difficulty),
        question_count=row.question_count,
        status=InterviewStatus(row.status),
        current_question_index=row.current_question_index,
        version=row.version,
        request_id=row.request_id,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        prepared_at=row.prepared_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _question_to_domain(
    row: InterviewQuestionModel, citations: Sequence[InterviewQuestionCitation]
) -> InterviewQuestion:
    return InterviewQuestion(
        id=row.id,
        session_id=row.session_id,
        sequence=row.sequence,
        content=row.content,
        category=row.category,
        difficulty=InterviewDifficulty(row.difficulty),
        expected_points=list(row.expected_points),
        source_summary=row.source_summary,
        created_at=row.created_at,
        citations=list(citations),
    )


def _citation_to_domain(row: InterviewQuestionCitationModel) -> InterviewQuestionCitation:
    return InterviewQuestionCitation(
        id=row.id,
        question_id=row.question_id,
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        source_id=row.source_id,
        page_number=row.page_number,
        score=float(row.score),
        excerpt=row.excerpt,
        ordinal=row.ordinal,
        created_at=row.created_at,
    )


def _event_to_domain(row: InterviewEventModel) -> InterviewEvent:
    return InterviewEvent(
        id=row.id,
        session_id=row.session_id,
        event_type=row.event_type,
        from_status=InterviewStatus(row.from_status) if row.from_status else None,
        to_status=InterviewStatus(row.to_status),
        payload=dict(row.payload),
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
    )
