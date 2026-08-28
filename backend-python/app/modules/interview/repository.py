from collections.abc import Sequence
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview.domain import (
    InterviewAnswer,
    InterviewDifficulty,
    InterviewEvaluation,
    InterviewEvent,
    InterviewProgress,
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    InterviewStatus,
    InterviewTurn,
    InterviewType,
    TurnStatus,
    TurnType,
    utc_now,
)
from app.modules.interview.exceptions import (
    InterviewNotFoundError,
    InterviewRequestAlreadyExistsError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.models import (
    InterviewAnswerModel,
    InterviewEvaluationModel,
    InterviewEventModel,
    InterviewQuestionCitationModel,
    InterviewQuestionModel,
    InterviewSessionModel,
    InterviewTurnModel,
)
from app.modules.interview.state_machine import InterviewStateMachine
from app.modules.knowledge.models import KnowledgeDocumentModel


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

    async def get_current_turn(self, session_id: UUID, user_id: UUID) -> InterviewTurn | None: ...

    async def get_turn_for_user(self, turn_id: UUID, user_id: UUID) -> InterviewTurn | None: ...

    async def list_turns(self, session_id: UUID, user_id: UUID) -> list[InterviewTurn]: ...

    async def find_answer_by_request(
        self, session_id: UUID, user_id: UUID, request_id: str
    ) -> InterviewProgress | None: ...

    async def get_answer_for_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> InterviewAnswer | None: ...

    async def get_evaluation_for_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> InterviewEvaluation | None: ...

    async def submit_answer(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        content: str,
        request_id: str,
    ) -> InterviewProgress: ...

    async def count_follow_ups(self, session_id: UUID) -> int: ...

    async def recent_answers(self, session_id: UUID, before_sequence: int) -> list[str]: ...

    async def persist_evaluation_and_progress(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        evaluation: InterviewEvaluation,
        decision_reason: str,
        should_follow_up: bool,
    ) -> InterviewSession: ...

    async def fail_evaluation(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        failure_code: str,
        failure_message: str,
    ) -> InterviewSession: ...

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
        question_result = await self._session.execute(
            select(InterviewQuestionModel)
            .where(
                InterviewQuestionModel.session_id == session_id,
                InterviewQuestionModel.sequence == 1,
            )
        )
        question = question_result.scalar_one_or_none()
        if question is None:
            raise InvalidInterviewTransitionError("Interview has no starting question")
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
        existing_turn = await self._session.scalar(
            select(InterviewTurnModel.id)
            .where(InterviewTurnModel.session_id == session_id)
            .limit(1)
        )
        if existing_turn is None:
            turn = InterviewTurnModel(
                id=uuid4(),
                session_id=session_id,
                question_id=question.id,
                parent_turn_id=None,
                sequence=1,
                turn_type=TurnType.PRIMARY.value,
                question_content=question.content,
                status=TurnStatus.WAITING_ANSWER.value,
                follow_up_depth=0,
                created_at=now,
            )
            self._session.add(turn)
            self._session.add(
                _event_row(
                    row.id,
                    "TURN_CREATED",
                    InterviewStatus.IN_PROGRESS,
                    InterviewStatus.IN_PROGRESS,
                    {"turn_sequence": 1},
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

    async def get_current_turn(self, session_id: UUID, user_id: UUID) -> InterviewTurn | None:
        session = await self.get_for_user(session_id, user_id)
        if session is None:
            return None
        result = await self._session.execute(
            select(InterviewTurnModel)
            .where(
                InterviewTurnModel.session_id == session_id,
                InterviewTurnModel.status.in_(
                    [TurnStatus.WAITING_ANSWER.value, TurnStatus.EVALUATING.value]
                ),
            )
            .order_by(InterviewTurnModel.sequence.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _turn_to_domain(row) if row is not None else None

    async def get_turn_for_user(self, turn_id: UUID, user_id: UUID) -> InterviewTurn | None:
        result = await self._session.execute(
            select(InterviewTurnModel)
            .join(InterviewSessionModel, InterviewSessionModel.id == InterviewTurnModel.session_id)
            .where(InterviewTurnModel.id == turn_id, InterviewSessionModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return _turn_to_domain(row) if row is not None else None

    async def list_turns(self, session_id: UUID, user_id: UUID) -> list[InterviewTurn]:
        session = await self.get_for_user(session_id, user_id)
        if session is None:
            return []
        result = await self._session.execute(
            select(InterviewTurnModel)
            .where(InterviewTurnModel.session_id == session_id)
            .order_by(InterviewTurnModel.sequence.asc())
        )
        return [_turn_to_domain(row) for row in result.scalars().all()]

    async def find_answer_by_request(
        self, session_id: UUID, user_id: UUID, request_id: str
    ) -> InterviewProgress | None:
        result = await self._session.execute(
            select(InterviewAnswerModel, InterviewTurnModel, InterviewSessionModel)
            .join(InterviewTurnModel, InterviewTurnModel.id == InterviewAnswerModel.turn_id)
            .join(
                InterviewSessionModel,
                InterviewSessionModel.id == InterviewAnswerModel.session_id,
            )
            .where(
                InterviewAnswerModel.session_id == session_id,
                InterviewAnswerModel.user_id == user_id,
                InterviewAnswerModel.request_id == request_id,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        answer_model, turn_model, session_model = row
        evaluation = await self._evaluation_for_turn_model(turn_model.id)
        return InterviewProgress(
            session=_session_to_domain(session_model),
            turn=_turn_to_domain(turn_model),
            answer=_answer_to_domain(answer_model),
            evaluation=evaluation,
        )

    async def get_answer_for_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> InterviewAnswer | None:
        result = await self._session.execute(
            select(InterviewAnswerModel)
            .join(
                InterviewSessionModel,
                InterviewSessionModel.id == InterviewAnswerModel.session_id,
            )
            .where(
                InterviewAnswerModel.turn_id == turn_id,
                InterviewSessionModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _answer_to_domain(row) if row is not None else None

    async def get_evaluation_for_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> InterviewEvaluation | None:
        result = await self._session.execute(
            select(InterviewEvaluationModel)
            .join(InterviewTurnModel, InterviewTurnModel.id == InterviewEvaluationModel.turn_id)
            .join(
                InterviewSessionModel,
                InterviewSessionModel.id == InterviewTurnModel.session_id,
            )
            .where(
                InterviewEvaluationModel.turn_id == turn_id,
                InterviewSessionModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _evaluation_to_domain(row) if row is not None else None

    async def submit_answer(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        content: str,
        request_id: str,
    ) -> InterviewProgress:
        session_row = await self._locked_row(session_id, user_id)
        if session_row is None:
            raise InterviewNotFoundError("Interview session not found")
        existing = await self.find_answer_by_request(session_id, user_id, request_id)
        if existing is not None:
            return existing
        turn_row = await self._locked_turn(turn_id, session_id)
        if turn_row is None:
            raise InterviewNotFoundError("Interview turn not found")
        if InterviewStatus(session_row.status) != InterviewStatus.IN_PROGRESS:
            raise InvalidInterviewTransitionError("Interview is not in progress")
        active = await self._session.scalar(
            select(InterviewTurnModel.id)
            .where(
                InterviewTurnModel.session_id == session_id,
                InterviewTurnModel.status.in_(
                    [TurnStatus.WAITING_ANSWER.value, TurnStatus.EVALUATING.value]
                ),
            )
            .order_by(InterviewTurnModel.sequence.desc())
            .limit(1)
        )
        if active != turn_id:
            raise InvalidInterviewTransitionError("Turn is not the current turn")
        if TurnStatus(turn_row.status) != TurnStatus.WAITING_ANSWER:
            raise InvalidInterviewTransitionError("Turn cannot accept another answer")
        if await self._session.scalar(
            select(InterviewAnswerModel.id).where(InterviewAnswerModel.turn_id == turn_id)
        ):
            raise InvalidInterviewTransitionError("Turn already has an answer")
        now = utc_now()
        answer_row = InterviewAnswerModel(
            id=uuid4(),
            turn_id=turn_id,
            session_id=session_id,
            user_id=user_id,
            content=content,
            request_id=request_id,
            created_at=now,
        )
        turn_row.status = TurnStatus.EVALUATING.value
        turn_row.answered_at = now
        session_row.version += 1
        session_row.updated_at = now
        self._session.add(answer_row)
        self._session.add(
            _event_row(
                session_id,
                "ANSWER_SUBMITTED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.IN_PROGRESS,
                {"turn_sequence": turn_row.sequence},
                request_id,
            )
        )
        self._session.add(
            _event_row(
                session_id,
                "EVALUATION_STARTED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.IN_PROGRESS,
                {"turn_sequence": turn_row.sequence},
                request_id,
            )
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            existing = await self.find_answer_by_request(session_id, user_id, request_id)
            if existing is not None:
                return existing
            raise InvalidInterviewTransitionError("Answer could not be submitted") from exc
        await self._session.refresh(session_row)
        await self._session.refresh(turn_row)
        return InterviewProgress(
            session=_session_to_domain(session_row),
            turn=_turn_to_domain(turn_row),
            answer=_answer_to_domain(answer_row),
        )

    async def count_follow_ups(self, session_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(
                select(InterviewTurnModel.id)
                .where(
                    InterviewTurnModel.session_id == session_id,
                    InterviewTurnModel.turn_type == TurnType.FOLLOW_UP.value,
                )
                .subquery()
            )
        )
        return int(count or 0)

    async def recent_answers(self, session_id: UUID, before_sequence: int) -> list[str]:
        result = await self._session.execute(
            select(InterviewAnswerModel.content)
            .join(InterviewTurnModel, InterviewTurnModel.id == InterviewAnswerModel.turn_id)
            .where(
                InterviewAnswerModel.session_id == session_id,
                InterviewTurnModel.sequence < before_sequence,
            )
            .order_by(InterviewTurnModel.sequence.desc())
            .limit(3)
        )
        return list(reversed(result.scalars().all()))

    async def persist_evaluation_and_progress(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        evaluation: InterviewEvaluation,
        decision_reason: str,
        should_follow_up: bool,
    ) -> InterviewSession:
        session_row = await self._locked_row(session_id, user_id)
        if session_row is None:
            raise InterviewNotFoundError("Interview session not found")
        turn_row = await self._locked_turn(turn_id, session_id)
        if turn_row is None:
            raise InterviewNotFoundError("Interview turn not found")
        existing = await self._session.scalar(
            select(InterviewEvaluationModel).where(InterviewEvaluationModel.turn_id == turn_id)
        )
        if existing is not None:
            return _session_to_domain(session_row)
        if TurnStatus(turn_row.status) != TurnStatus.EVALUATING:
            raise InvalidInterviewTransitionError("Turn is not being evaluated")
        evaluation_row = InterviewEvaluationModel(
            id=evaluation.id,
            turn_id=turn_id,
            overall_score=evaluation.overall_score,
            technical_score=evaluation.technical_score,
            relevance_score=evaluation.relevance_score,
            clarity_score=evaluation.clarity_score,
            depth_score=evaluation.depth_score,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            feedback=evaluation.feedback,
            suggested_improvements=evaluation.suggested_improvements,
            llm_should_follow_up=evaluation.llm_should_follow_up,
            follow_up_focus=evaluation.follow_up_focus,
            follow_up_question=evaluation.follow_up_question,
            created_at=evaluation.created_at,
        )
        now = utc_now()
        turn_row.status = TurnStatus.COMPLETED.value
        turn_row.evaluated_at = now
        session_row.version += 1
        session_row.updated_at = now
        self._session.add(evaluation_row)
        self._session.add(
            _event_row(
                session_id,
                "ANSWER_EVALUATED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.IN_PROGRESS,
                {"turn_sequence": turn_row.sequence, "overall_score": evaluation.overall_score},
                None,
            )
        )
        self._session.add(
            _event_row(
                session_id,
                "FOLLOW_UP_DECIDED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.IN_PROGRESS,
                {"should_follow_up": should_follow_up, "reason": decision_reason},
                None,
            )
        )
        if should_follow_up:
            if not evaluation.follow_up_question:
                raise InvalidInterviewTransitionError("Follow-up question is missing")
            next_turn = InterviewTurnModel(
                id=uuid4(),
                session_id=session_id,
                question_id=None,
                parent_turn_id=turn_id,
                sequence=await self._next_turn_sequence(session_id),
                turn_type=TurnType.FOLLOW_UP.value,
                question_content=evaluation.follow_up_question,
                status=TurnStatus.WAITING_ANSWER.value,
                follow_up_depth=turn_row.follow_up_depth + 1,
                created_at=now,
            )
            self._session.add(next_turn)
            self._session.add(
                _event_row(
                    session_id,
                    "FOLLOW_UP_CREATED",
                    InterviewStatus.IN_PROGRESS,
                    InterviewStatus.IN_PROGRESS,
                    {"turn_sequence": next_turn.sequence, "parent_sequence": turn_row.sequence},
                    None,
                )
            )
        else:
            next_sequence = session_row.current_question_index + 2
            question = await self._session.scalar(
                select(InterviewQuestionModel).where(
                    InterviewQuestionModel.session_id == session_id,
                    InterviewQuestionModel.sequence == next_sequence,
                )
            )
            if question is None:
                session_row.status = InterviewStatus.COMPLETED.value
                session_row.finished_at = now
                self._session.add(
                    _event_row(
                        session_id,
                        "INTERVIEW_COMPLETED",
                        InterviewStatus.IN_PROGRESS,
                        InterviewStatus.COMPLETED,
                        {"completed_sequence": turn_row.sequence},
                        None,
                    )
                )
            else:
                session_row.current_question_index += 1
                next_turn = InterviewTurnModel(
                    id=uuid4(),
                    session_id=session_id,
                    question_id=question.id,
                    parent_turn_id=None,
                    sequence=await self._next_turn_sequence(session_id),
                    turn_type=TurnType.PRIMARY.value,
                    question_content=question.content,
                    status=TurnStatus.WAITING_ANSWER.value,
                    follow_up_depth=0,
                    created_at=now,
                )
                self._session.add(next_turn)
                self._session.add(
                    _event_row(
                        session_id,
                        "NEXT_QUESTION_CREATED",
                        InterviewStatus.IN_PROGRESS,
                        InterviewStatus.IN_PROGRESS,
                        {"turn_sequence": next_turn.sequence, "question_sequence": next_sequence},
                        None,
                    )
                )
        self._session.add(
            _event_row(
                session_id,
                "TURN_COMPLETED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.IN_PROGRESS,
                {"turn_sequence": turn_row.sequence},
                None,
            )
        )
        await self._session.commit()
        await self._session.refresh(session_row)
        return _session_to_domain(session_row)

    async def fail_evaluation(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        failure_code: str,
        failure_message: str,
    ) -> InterviewSession:
        # Clear any uncommitted evaluation work before recording the terminal failure.
        await self._session.rollback()
        session_row = await self._locked_row(session_id, user_id)
        if session_row is None:
            raise InterviewNotFoundError("Interview session not found")
        turn_row = await self._locked_turn(turn_id, session_id)
        if turn_row is None:
            raise InterviewNotFoundError("Interview turn not found")
        if InterviewStatus(session_row.status) in {
            InterviewStatus.FAILED,
            InterviewStatus.COMPLETED,
            InterviewStatus.CANCELLED,
        } or TurnStatus(turn_row.status) in {TurnStatus.COMPLETED, TurnStatus.FAILED}:
            return _session_to_domain(session_row)
        now = utc_now()
        await self._session.execute(
            delete(InterviewEvaluationModel).where(InterviewEvaluationModel.turn_id == turn_id)
        )
        turn_row.status = TurnStatus.FAILED.value
        turn_row.evaluated_at = now
        session_row.status = InterviewStatus.FAILED.value
        session_row.failure_code = failure_code[:64]
        session_row.failure_message = failure_message[:2000]
        session_row.updated_at = now
        session_row.version += 1
        self._session.add(
            _event_row(
                session_id,
                "TURN_FAILED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.FAILED,
                {"turn_sequence": turn_row.sequence, "failure_code": session_row.failure_code},
                None,
            )
        )
        self._session.add(
            _event_row(
                session_id,
                "INTERVIEW_FAILED",
                InterviewStatus.IN_PROGRESS,
                InterviewStatus.FAILED,
                {"failure_code": session_row.failure_code},
                None,
            )
        )
        await self._session.commit()
        await self._session.refresh(session_row)
        return _session_to_domain(session_row)

    async def _locked_turn(self, turn_id: UUID, session_id: UUID) -> InterviewTurnModel | None:
        result = await self._session.execute(
            select(InterviewTurnModel)
            .where(InterviewTurnModel.id == turn_id, InterviewTurnModel.session_id == session_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _next_turn_sequence(self, session_id: UUID) -> int:
        maximum = await self._session.scalar(
            select(func.max(InterviewTurnModel.sequence)).where(
                InterviewTurnModel.session_id == session_id
            )
        )
        return int(maximum or 0) + 1

    async def _evaluation_for_turn_model(self, turn_id: UUID) -> InterviewEvaluation | None:
        row = await self._session.scalar(
            select(InterviewEvaluationModel).where(InterviewEvaluationModel.turn_id == turn_id)
        )
        return _evaluation_to_domain(row) if row is not None else None

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
            select(InterviewQuestionCitationModel, KnowledgeDocumentModel.original_filename)
            .outerjoin(
                KnowledgeDocumentModel,
                KnowledgeDocumentModel.id == InterviewQuestionCitationModel.document_id,
            )
            .where(InterviewQuestionCitationModel.question_id.in_([row.id for row in rows]))
            .order_by(
                InterviewQuestionCitationModel.question_id,
                InterviewQuestionCitationModel.ordinal,
            )
        )
        by_question: dict[UUID, list[InterviewQuestionCitation]] = {}
        for citation, document_name in citation_result.all():
            by_question.setdefault(citation.question_id, []).append(
                _citation_to_domain(citation, document_name)
            )
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


def _citation_to_domain(
    row: InterviewQuestionCitationModel, document_name: str | None = None
) -> InterviewQuestionCitation:
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
        document_name=document_name,
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


def _turn_to_domain(row: InterviewTurnModel) -> InterviewTurn:
    return InterviewTurn(
        id=row.id,
        session_id=row.session_id,
        question_id=row.question_id,
        parent_turn_id=row.parent_turn_id,
        sequence=row.sequence,
        turn_type=TurnType(row.turn_type),
        question_content=row.question_content,
        status=TurnStatus(row.status),
        follow_up_depth=row.follow_up_depth,
        created_at=row.created_at,
        answered_at=row.answered_at,
        evaluated_at=row.evaluated_at,
    )


def _answer_to_domain(row: InterviewAnswerModel) -> InterviewAnswer:
    return InterviewAnswer(
        id=row.id,
        turn_id=row.turn_id,
        session_id=row.session_id,
        user_id=row.user_id,
        content=row.content,
        request_id=row.request_id,
        created_at=row.created_at,
    )


def _evaluation_to_domain(row: InterviewEvaluationModel) -> InterviewEvaluation:
    return InterviewEvaluation(
        id=row.id,
        turn_id=row.turn_id,
        overall_score=row.overall_score,
        technical_score=row.technical_score,
        relevance_score=row.relevance_score,
        clarity_score=row.clarity_score,
        depth_score=row.depth_score,
        strengths=list(row.strengths),
        weaknesses=list(row.weaknesses),
        feedback=row.feedback,
        suggested_improvements=list(row.suggested_improvements),
        llm_should_follow_up=row.llm_should_follow_up,
        follow_up_focus=row.follow_up_focus,
        follow_up_question=row.follow_up_question,
        created_at=row.created_at,
    )
