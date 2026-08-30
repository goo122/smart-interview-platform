from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.ai.interview import (
    FakeInterviewQuestionGenerator,
    GeneratedInterviewQuestion,
    GeneratedQuestionSet,
)
from app.core.config import Settings
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.interview.context import InterviewContext
from app.modules.interview.dependencies import get_interview_service
from app.modules.interview.domain import (
    InterviewAnswer,
    InterviewDifficulty,
    InterviewEvaluation,
    InterviewEvent,
    InterviewProgress,
    InterviewQuestion,
    InterviewSession,
    InterviewStatus,
    InterviewTurn,
    InterviewType,
    ResumeEvaluation,
    TurnStatus,
    TurnType,
    utc_now,
)
from app.modules.interview.exceptions import (
    InterviewFinishWithoutCompletedAnswersError,
    InterviewKnowledgeUnavailableError,
    InterviewNotFoundError,
    InterviewPreparationQueueUnavailableError,
    InvalidInterviewRequestError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.service import InterviewService
from app.modules.interview.state_machine import InterviewStateMachine
from app.modules.knowledge.context import ContextCitation
from app.workers.queue import InterviewPreparationJob


class InMemoryInterviewRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, InterviewSession] = {}
        self.questions: dict[UUID, list[InterviewQuestion]] = {}
        self.events: dict[UUID, list[InterviewEvent]] = {}
        self.turns: dict[UUID, list[InterviewTurn]] = {}
        self.answers: dict[UUID, InterviewAnswer] = {}
        self.evaluations: dict[UUID, InterviewEvaluation] = {}
        self.resume_evaluations: dict[UUID, ResumeEvaluation] = {}

    async def get_resume_evaluation(
        self, session_id: UUID, user_id: UUID
    ) -> ResumeEvaluation | None:
        evaluation = self.resume_evaluations.get(session_id)
        return evaluation if evaluation and evaluation.user_id == user_id else None

    async def create(self, session: InterviewSession) -> InterviewSession:
        self.sessions[session.id] = session
        self.events[session.id] = [
            InterviewEvent(
                id=uuid4(),
                session_id=session.id,
                event_type="SESSION_CREATED",
                from_status=None,
                to_status=InterviewStatus.CREATED,
                payload={"request_id_present": session.request_id is not None},
                idempotency_key=session.request_id,
                created_at=utc_now(),
            )
        ]
        self.turns[session.id] = []
        return session

    async def find_by_request(self, user_id: UUID, request_id: str) -> InterviewSession | None:
        return next(
            (
                session
                for session in self.sessions.values()
                if session.user_id == user_id and session.request_id == request_id
            ),
            None,
        )

    async def get_for_user(self, session_id: UUID, user_id: UUID) -> InterviewSession | None:
        session = self.sessions.get(session_id)
        return session if session and session.user_id == user_id else None

    async def list_for_user(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[InterviewSession], int]:
        values = [session for session in self.sessions.values() if session.user_id == user_id]
        start = (current - 1) * size
        return values[start : start + size], len(values)

    async def list_conversations_for_user(
        self,
        user_id: UUID,
        current: int,
        size: int,
        status: InterviewStatus | None = None,
        keyword: str | None = None,
    ) -> tuple[list[InterviewSession], int]:
        values = [session for session in self.sessions.values() if session.user_id == user_id]
        if status is not None:
            values = [session for session in values if session.status == status]
        clean_keyword = keyword.strip().casefold() if keyword else ""
        if clean_keyword:
            values = [
                session
                for session in values
                if clean_keyword in session.job_title.casefold()
                or clean_keyword in session.job_description.casefold()
            ]
        values.sort(key=lambda session: session.updated_at, reverse=True)
        start = (current - 1) * size
        return values[start : start + size], len(values)

    async def begin_preparing(
        self, session_id: UUID, user_id: UUID
    ) -> tuple[InterviewSession, bool]:
        session = self.sessions[session_id]
        if session.user_id != user_id:
            raise InvalidInterviewRequestError("not found")
        if session.status != InterviewStatus.CREATED:
            return session, False
        session.status = InterviewStatus.PREPARING
        session.version += 1
        session.updated_at = utc_now()
        self.events[session.id].append(
            self._event(session, InterviewStatus.CREATED, InterviewStatus.PREPARING)
        )
        return session, True

    async def persist_questions_and_ready(
        self, session_id: UUID, user_id: UUID, questions: list[InterviewQuestion]
    ) -> InterviewSession:
        session = self.sessions[session_id]
        assert session.user_id == user_id
        self.questions[session_id] = list(questions)
        session.status = InterviewStatus.READY
        session.prepared_at = utc_now()
        session.version += 1
        session.updated_at = session.prepared_at
        self.events[session.id].append(
            self._event(session, InterviewStatus.PREPARING, InterviewStatus.READY)
        )
        return session

    async def mark_failed(
        self, session_id: UUID, user_id: UUID, failure_code: str, failure_message: str
    ) -> InterviewSession:
        session = self.sessions[session_id]
        assert session.user_id == user_id
        if session.status not in {InterviewStatus.FAILED, InterviewStatus.CANCELLED}:
            previous = session.status
            session.status = InterviewStatus.FAILED
            session.failure_code = failure_code
            session.failure_message = failure_message
            session.version += 1
            session.updated_at = utc_now()
            self.questions.pop(session_id, None)
            self.events[session.id].append(self._event(session, previous, InterviewStatus.FAILED))
        return session

    async def start(self, session_id: UUID, user_id: UUID) -> InterviewSession:
        session = self.sessions[session_id]
        assert session.user_id == user_id
        if session.status == InterviewStatus.IN_PROGRESS:
            if not self.turns[session.id]:
                question = self.questions[session_id][0]
                self.turns[session.id].append(
                    InterviewTurn(
                        id=uuid4(),
                        session_id=session_id,
                        question_id=question.id,
                        parent_turn_id=None,
                        sequence=1,
                        turn_type=TurnType.PRIMARY,
                        question_content=question.content,
                        status=TurnStatus.WAITING_ANSWER,
                        follow_up_depth=0,
                        created_at=utc_now(),
                        answered_at=None,
                        evaluated_at=None,
                    )
                )
            return session
        if session.status != InterviewStatus.READY:
            raise InvalidInterviewTransitionError("not ready")
        previous = session.status
        session.status = InterviewStatus.IN_PROGRESS
        session.started_at = utc_now()
        session.version += 1
        session.updated_at = session.started_at
        self.events[session.id].append(self._event(session, previous, session.status))
        question = self.questions[session_id][0]
        self.turns[session.id].append(
            InterviewTurn(
                id=uuid4(),
                session_id=session_id,
                question_id=question.id,
                parent_turn_id=None,
                sequence=1,
                turn_type=TurnType.PRIMARY,
                question_content=question.content,
                status=TurnStatus.WAITING_ANSWER,
                follow_up_depth=0,
                created_at=utc_now(),
                answered_at=None,
                evaluated_at=None,
            )
        )
        return session

    async def cancel(self, session_id: UUID, user_id: UUID) -> InterviewSession:
        session = self.sessions[session_id]
        assert session.user_id == user_id
        if session.status == InterviewStatus.CANCELLED:
            return session
        if session.status not in {
            InterviewStatus.CREATED,
            InterviewStatus.PREPARING,
            InterviewStatus.READY,
        }:
            raise InvalidInterviewTransitionError("cannot cancel")
        previous = session.status
        session.status = InterviewStatus.CANCELLED
        session.finished_at = utc_now()
        session.updated_at = session.finished_at
        session.version += 1
        self.events[session.id].append(self._event(session, previous, session.status))
        return session

    async def finish(self, session_id: UUID, user_id: UUID) -> InterviewSession:
        session = self.sessions[session_id]
        assert session.user_id == user_id
        if session.status == InterviewStatus.COMPLETED:
            return session
        if session.status != InterviewStatus.IN_PROGRESS:
            raise InvalidInterviewTransitionError("cannot finish")
        completed_turn_ids = {
            turn.id
            for turn in self.turns[session_id]
            if turn.status == TurnStatus.COMPLETED
            and turn.id in self.answers
            and turn.id in self.evaluations
        }
        if not completed_turn_ids:
            raise InterviewFinishWithoutCompletedAnswersError(
                "至少完成并提交一道题后才能结束面试并生成报告"
            )

        skipped_sequences: list[int] = []
        for turn in self.turns[session_id]:
            if turn.status not in {TurnStatus.WAITING_ANSWER, TurnStatus.EVALUATING}:
                continue
            turn.status = TurnStatus.SKIPPED
            skipped_sequences.append(turn.sequence)
            self.events[session_id].append(
                InterviewEvent(
                    id=uuid4(),
                    session_id=session_id,
                    event_type="TURN_SKIPPED",
                    from_status=InterviewStatus.IN_PROGRESS,
                    to_status=InterviewStatus.IN_PROGRESS,
                    payload={"turn_sequence": turn.sequence, "reason": "EARLY_FINISH"},
                    idempotency_key=f"finish:{session_id}:turn:{turn.id}",
                    created_at=utc_now(),
                )
            )

        represented_question_ids = {
            turn.question_id
            for turn in self.turns[session_id]
            if turn.question_id is not None
        }
        next_sequence = max(
            (turn.sequence for turn in self.turns[session_id]), default=0
        ) + 1
        for question in self.questions.get(session_id, []):
            if question.id in represented_question_ids:
                continue
            self.turns[session_id].append(
                InterviewTurn(
                    id=uuid4(),
                    session_id=session_id,
                    question_id=question.id,
                    parent_turn_id=None,
                    sequence=next_sequence,
                    turn_type=TurnType.PRIMARY,
                    question_content=question.content,
                    status=TurnStatus.SKIPPED,
                    follow_up_depth=0,
                    created_at=utc_now(),
                    answered_at=None,
                    evaluated_at=None,
                )
            )
            skipped_sequences.append(next_sequence)
            next_sequence += 1

        previous = session.status
        session.status = InterviewStatus.COMPLETED
        session.finished_at = utc_now()
        session.updated_at = session.finished_at
        session.version += 1
        self.events[session_id].append(
            InterviewEvent(
                id=uuid4(),
                session_id=session_id,
                event_type="INTERVIEW_FINISHED_EARLY",
                from_status=previous,
                to_status=InterviewStatus.COMPLETED,
                payload={
                    "finish_mode": "EARLY",
                    "completed_turn_count": len(completed_turn_ids),
                    "skipped_turn_count": len(skipped_sequences),
                    "skipped_turn_sequences": skipped_sequences,
                    "version": session.version,
                },
                idempotency_key=f"finish:{session_id}",
                created_at=utc_now(),
            )
        )
        return session

    async def list_questions(self, session_id: UUID) -> list[InterviewQuestion]:
        return self.questions.get(session_id, [])

    async def list_events(self, session_id: UUID) -> list[InterviewEvent]:
        return self.events.get(session_id, [])

    async def get_current_turn(self, session_id: UUID, user_id: UUID) -> InterviewTurn | None:
        session = await self.get_for_user(session_id, user_id)
        if session is None:
            return None
        active = [
            turn
            for turn in self.turns[session_id]
            if turn.status in {TurnStatus.WAITING_ANSWER, TurnStatus.EVALUATING}
        ]
        return max(active, key=lambda turn: turn.sequence) if active else None

    async def get_turn_for_user(self, turn_id: UUID, user_id: UUID) -> InterviewTurn | None:
        for turns in self.turns.values():
            for turn in turns:
                if turn.id == turn_id:
                    session = await self.get_for_user(turn.session_id, user_id)
                    return turn if session else None
        return None

    async def list_turns(self, session_id: UUID, user_id: UUID) -> list[InterviewTurn]:
        if await self.get_for_user(session_id, user_id) is None:
            return []
        return sorted(self.turns[session_id], key=lambda turn: turn.sequence)

    async def find_answer_by_request(
        self, session_id: UUID, user_id: UUID, request_id: str
    ) -> InterviewProgress | None:
        for answer in self.answers.values():
            if (
                answer.session_id == session_id
                and answer.user_id == user_id
                and answer.request_id == request_id
            ):
                turn = next(turn for turn in self.turns[session_id] if turn.id == answer.turn_id)
                return InterviewProgress(
                    session=self.sessions[session_id],
                    turn=turn,
                    answer=answer,
                    evaluation=self.evaluations.get(turn.id),
                )
        return None

    async def get_answer_for_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> InterviewAnswer | None:
        answer = self.answers.get(turn_id)
        if answer is None or await self.get_for_user(answer.session_id, user_id) is None:
            return None
        return answer

    async def get_evaluation_for_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> InterviewEvaluation | None:
        evaluation = self.evaluations.get(turn_id)
        if evaluation is None:
            return None
        turn = await self.get_turn_for_user(turn_id, user_id)
        return evaluation if turn else None

    async def submit_answer(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        content: str,
        request_id: str,
    ) -> InterviewProgress:
        existing = await self.find_answer_by_request(session_id, user_id, request_id)
        if existing:
            return existing
        turn = next(turn for turn in self.turns[session_id] if turn.id == turn_id)
        if turn.status != TurnStatus.WAITING_ANSWER:
            raise InvalidInterviewTransitionError("turn is not waiting")
        answer = InterviewAnswer(
            id=uuid4(),
            turn_id=turn_id,
            session_id=session_id,
            user_id=user_id,
            content=content,
            request_id=request_id,
            created_at=utc_now(),
        )
        turn.status = TurnStatus.EVALUATING
        turn.answered_at = answer.created_at
        self.answers[turn_id] = answer
        return InterviewProgress(self.sessions[session_id], turn, answer, None)

    async def count_follow_ups(self, session_id: UUID) -> int:
        return sum(
            turn.turn_type == TurnType.FOLLOW_UP for turn in self.turns[session_id]
        )

    async def recent_answers(self, session_id: UUID, before_sequence: int) -> list[str]:
        values = [
            self.answers[turn.id].content
            for turn in sorted(self.turns[session_id], key=lambda item: item.sequence)
            if turn.sequence < before_sequence and turn.id in self.answers
        ]
        return values[-3:]

    async def persist_evaluation_and_progress(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        evaluation: InterviewEvaluation,
        decision_reason: str,
        should_follow_up: bool,
    ) -> InterviewSession:
        del decision_reason
        session = self.sessions[session_id]
        turn = next(turn for turn in self.turns[session_id] if turn.id == turn_id)
        if turn.id in self.evaluations:
            return session
        self.evaluations[turn_id] = evaluation
        turn.status = TurnStatus.COMPLETED
        turn.evaluated_at = utc_now()
        if should_follow_up:
            self.turns[session_id].append(
                InterviewTurn(
                    id=uuid4(),
                    session_id=session_id,
                    question_id=None,
                    parent_turn_id=turn_id,
                    sequence=len(self.turns[session_id]) + 1,
                    turn_type=TurnType.FOLLOW_UP,
                    question_content=evaluation.follow_up_question or "请进一步说明。",
                    status=TurnStatus.WAITING_ANSWER,
                    follow_up_depth=turn.follow_up_depth + 1,
                    created_at=utc_now(),
                    answered_at=None,
                    evaluated_at=None,
                )
            )
        else:
            next_question = next(
                (
                    question
                    for question in self.questions[session_id]
                    if question.sequence == session.current_question_index + 2
                ),
                None,
            )
            if next_question is None:
                session.status = InterviewStatus.COMPLETED
                session.finished_at = utc_now()
            else:
                session.current_question_index += 1
                self.turns[session_id].append(
                    InterviewTurn(
                        id=uuid4(),
                        session_id=session_id,
                        question_id=next_question.id,
                        parent_turn_id=None,
                        sequence=len(self.turns[session_id]) + 1,
                        turn_type=TurnType.PRIMARY,
                        question_content=next_question.content,
                        status=TurnStatus.WAITING_ANSWER,
                        follow_up_depth=0,
                        created_at=utc_now(),
                        answered_at=None,
                        evaluated_at=None,
                    )
                )
        return session

    async def fail_evaluation(
        self,
        session_id: UUID,
        turn_id: UUID,
        user_id: UUID,
        failure_code: str,
        failure_message: str,
    ) -> InterviewSession:
        del user_id
        session = self.sessions[session_id]
        turn = next(turn for turn in self.turns[session_id] if turn.id == turn_id)
        turn.status = TurnStatus.FAILED
        session.status = InterviewStatus.FAILED
        session.failure_code = failure_code
        session.failure_message = failure_message
        return session

    @staticmethod
    def _event(
        session: InterviewSession, previous: InterviewStatus, target: InterviewStatus
    ) -> InterviewEvent:
        return InterviewEvent(
            id=uuid4(),
            session_id=session.id,
            event_type="STATUS_CHANGED",
            from_status=previous,
            to_status=target,
            payload={"version": session.version},
            idempotency_key=session.request_id,
            created_at=utc_now(),
        )


class FakeInterviewContextProvider:
    def __init__(
        self, context: InterviewContext | None = None, error: Exception | None = None
    ) -> None:
        self.context = context
        self.error = error
        self.validated: list[tuple[UUID, UUID]] = []
        self.build_calls = 0

    async def validate_knowledge_base(self, user_id: UUID, knowledge_base_id: UUID) -> None:
        self.validated.append((user_id, knowledge_base_id))

    async def build(self, **_kwargs: object) -> InterviewContext:
        self.build_calls += 1
        if self.error:
            raise self.error
        if self.context is None:
            raise InterviewKnowledgeUnavailableError("No ready resume content was found")
        return self.context


class FakeTaskQueue:
    def __init__(self, run_immediately: bool = True) -> None:
        self.run_immediately = run_immediately
        self.tasks: list[Callable[[], Awaitable[None]]] = []

    async def enqueue(self, task: Callable[[], Awaitable[None]]) -> None:
        self.tasks.append(task)
        if self.run_immediately:
            await task()


class DeferredInterviewPreparationQueue:
    def __init__(self) -> None:
        self.jobs: list[InterviewPreparationJob] = []

    async def enqueue_interview_preparation(self, job: InterviewPreparationJob) -> None:
        self.jobs.append(job)


class FailingInterviewPreparationQueue:
    async def enqueue_interview_preparation(self, _job: InterviewPreparationJob) -> None:
        raise RuntimeError("redis unavailable")


def _context() -> InterviewContext:
    return InterviewContext(
        prompt="resume context",
        citations=(
            ContextCitation(
                source_id="[S1]",
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="resume.pdf",
                page_number=2,
                score=0.9,
                excerpt="FastAPI project",
                ordinal=0,
            ),
        ),
    )


def _service(
    *,
    context: InterviewContext | None = None,
    output: GeneratedQuestionSet | None = None,
    error: Exception | None = None,
    queue: FakeTaskQueue | None = None,
) -> tuple[
    InterviewService,
    InMemoryInterviewRepository,
    FakeInterviewContextProvider,
    FakeInterviewQuestionGenerator,
]:
    repository = InMemoryInterviewRepository()
    provider = FakeInterviewContextProvider(context, error)
    generator = FakeInterviewQuestionGenerator(output=output, error=error)
    service = InterviewService(
        repository,
        provider,
        generator,
        queue or FakeTaskQueue(),
        Settings(),
    )
    return service, repository, provider, generator


def _create_args(user_id: UUID, base_id: UUID, request_id: str | None = None) -> dict[str, object]:
    return {
        "user_id": user_id,
        "knowledge_base_id": base_id,
        "job_title": "Python 后端工程师",
        "job_description": "负责 FastAPI 和 PostgreSQL 应用开发",
        "interview_type": InterviewType.TECHNICAL,
        "difficulty": InterviewDifficulty.MEDIUM,
        "question_count": 3,
        "request_id": request_id,
    }


def _seed_conversation(
    repository: InMemoryInterviewRepository,
    user_id: UUID,
    status: InterviewStatus,
    title: str,
    updated_at: datetime,
) -> InterviewSession:
    session = InterviewSession.new(
        user_id=user_id,
        knowledge_base_id=uuid4(),
        job_title=title,
        job_description=f"为 {title} 准备面试",
        interview_type=InterviewType.TECHNICAL,
        difficulty=InterviewDifficulty.MEDIUM,
        question_count=3,
        request_id=None,
    )
    session.status = status
    session.updated_at = updated_at
    repository.sessions[session.id] = session
    repository.events[session.id] = []
    repository.turns[session.id] = []
    return session


def _mark_first_turn_completed(
    repository: InMemoryInterviewRepository, session: InterviewSession, user_id: UUID
) -> None:
    turn = repository.turns[session.id][0]
    now = utc_now()
    turn.status = TurnStatus.COMPLETED
    turn.answered_at = now
    turn.evaluated_at = now
    repository.answers[turn.id] = InterviewAnswer(
        id=uuid4(),
        turn_id=turn.id,
        session_id=session.id,
        user_id=user_id,
        content="我完成了方案设计并验证了结果。",
        request_id="finish-answer-1",
        created_at=now,
    )
    repository.evaluations[turn.id] = InterviewEvaluation(
        id=uuid4(),
        turn_id=turn.id,
        overall_score=88,
        technical_score=90,
        relevance_score=88,
        clarity_score=86,
        depth_score=87,
        strengths=["结构清晰"],
        weaknesses=["可以补充更多指标"],
        feedback="回答完成了评分。",
        suggested_improvements=["补充量化结果"],
        llm_should_follow_up=False,
        follow_up_focus=None,
        follow_up_question=None,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_state_machine_transitions_and_invalid_states() -> None:
    machine = InterviewStateMachine()
    machine.transition(InterviewStatus.CREATED, InterviewStatus.PREPARING)
    machine.transition(InterviewStatus.PREPARING, InterviewStatus.READY)
    machine.transition(InterviewStatus.READY, InterviewStatus.IN_PROGRESS)
    with pytest.raises(InvalidInterviewTransitionError):
        machine.transition(InterviewStatus.FAILED, InterviewStatus.IN_PROGRESS)


@pytest.mark.asyncio
async def test_preparation_generates_questions_citations_and_events() -> None:
    user_id, base_id = uuid4(), uuid4()
    service, repository, provider, generator = _service(context=_context())
    session = await service.create_session(**_create_args(user_id, base_id, "request-1"))

    assert session.status == InterviewStatus.READY
    assert len(await repository.list_questions(session.id)) == 3
    questions = await repository.list_questions(session.id)
    assert questions[0].citations
    assert [event.to_status for event in await repository.list_events(session.id)] == [
        InterviewStatus.CREATED,
        InterviewStatus.PREPARING,
        InterviewStatus.READY,
    ]
    assert provider.build_calls == 1
    assert generator.calls == 1
    assert generator.requests[0].source_ids == ("[S1]",)


@pytest.mark.asyncio
async def test_interview_creation_enqueues_preparation_and_returns_immediately() -> None:
    user_id, base_id = uuid4(), uuid4()
    repository = InMemoryInterviewRepository()
    provider = FakeInterviewContextProvider(_context())
    generator = FakeInterviewQuestionGenerator()
    queue = DeferredInterviewPreparationQueue()
    service = InterviewService(repository, provider, generator, queue, Settings())

    session = await service.create_session(**_create_args(user_id, base_id, "async-prepare"))

    assert session.status == InterviewStatus.PREPARING
    assert generator.calls == 0
    assert len(queue.jobs) == 1
    assert queue.jobs[0].session_id == session.id
    assert queue.jobs[0].user_id == user_id
    repeated = await service.create_session(**_create_args(user_id, base_id, "async-prepare"))
    assert repeated.id == session.id
    assert len(queue.jobs) == 1


@pytest.mark.asyncio
async def test_interview_queue_failure_is_safe_and_does_not_run_generator() -> None:
    user_id, base_id = uuid4(), uuid4()
    repository = InMemoryInterviewRepository()
    provider = FakeInterviewContextProvider(_context())
    generator = FakeInterviewQuestionGenerator()
    service = InterviewService(
        repository,
        provider,
        generator,
        FailingInterviewPreparationQueue(),
        Settings(),
    )

    with pytest.raises(InterviewPreparationQueueUnavailableError):
        await service.create_session(**_create_args(user_id, base_id, "queue-failure"))

    failed = next(iter(repository.sessions.values()))
    assert failed.status == InterviewStatus.FAILED
    assert failed.failure_code == "INTERVIEW_QUEUE_FAILED"
    assert generator.calls == 0


@pytest.mark.asyncio
async def test_request_id_is_idempotent_and_failed_output_cleans_questions() -> None:
    user_id, base_id = uuid4(), uuid4()
    service, repository, _, generator = _service(context=_context())
    first = await service.create_session(**_create_args(user_id, base_id, "same"))
    second = await service.create_session(**_create_args(user_id, base_id, "same"))
    assert first.id == second.id
    assert generator.calls == 1

    bad_output = GeneratedQuestionSet(
        questions=[
            GeneratedInterviewQuestion(
                content="duplicate",
                category="TECH",
                difficulty="MEDIUM",
                expected_points=["x"],
                source_ids=["[S1]"],
            ),
            GeneratedInterviewQuestion(
                content="duplicate",
                category="TECH",
                difficulty="MEDIUM",
                expected_points=["x"],
                source_ids=["[S1]"],
            ),
            GeneratedInterviewQuestion(
                content="third",
                category="TECH",
                difficulty="MEDIUM",
                expected_points=["x"],
                source_ids=["[S1]"],
            ),
        ]
    )
    bad_service, bad_repo, _, _ = _service(context=_context(), output=bad_output)
    failed = await bad_service.create_session(**_create_args(uuid4(), uuid4()))
    assert failed.status == InterviewStatus.FAILED
    assert failed.failure_code == "interview_questions_invalid"
    assert await bad_repo.list_questions(failed.id) == []


@pytest.mark.asyncio
async def test_start_cancel_permissions_and_ready_requirement() -> None:
    user_id, base_id = uuid4(), uuid4()
    queue = FakeTaskQueue(run_immediately=False)
    service, repository, _, _ = _service(context=_context(), queue=queue)
    session = await service.create_session(**_create_args(user_id, base_id))
    with pytest.raises(InvalidInterviewTransitionError):
        await service.start(user_id, session.id)
    await queue.tasks[0]()
    ready = await service.get_session(user_id, session.id)
    started = await service.start(user_id, ready.id)
    assert started.status == InterviewStatus.IN_PROGRESS
    assert (await service.start(user_id, ready.id)).version == started.version
    with pytest.raises(InvalidInterviewTransitionError):
        await service.cancel(user_id, ready.id)
    assert await repository.list_events(ready.id)


@pytest.mark.asyncio
async def test_early_finish_preserves_data_skips_turns_and_is_idempotent() -> None:
    user_id, base_id = uuid4(), uuid4()
    service, repository, _, _ = _service(context=_context())
    session = await service.create_session(**_create_args(user_id, base_id))
    started = await service.start(user_id, session.id)
    _mark_first_turn_completed(repository, started, user_id)

    finished = await service.finish(user_id, session.id)
    repeated = await service.finish(user_id, session.id)

    assert finished.status == InterviewStatus.COMPLETED
    assert repeated.version == finished.version
    first_turn = repository.turns[session.id][0]
    assert first_turn.status == TurnStatus.COMPLETED
    assert repository.answers[first_turn.id].content.startswith("我完成了")
    assert repository.evaluations[first_turn.id].overall_score == 88
    assert [turn.status for turn in repository.turns[session.id]] == [
        TurnStatus.COMPLETED,
        TurnStatus.SKIPPED,
        TurnStatus.SKIPPED,
    ]
    events = await repository.list_events(session.id)
    assert sum(event.event_type == "INTERVIEW_FINISHED_EARLY" for event in events) == 1


@pytest.mark.asyncio
async def test_early_finish_without_completed_answer_is_rejected() -> None:
    user_id, base_id = uuid4(), uuid4()
    service, _, _, _ = _service(context=_context())
    session = await service.create_session(**_create_args(user_id, base_id))
    await service.start(user_id, session.id)

    with pytest.raises(InterviewFinishWithoutCompletedAnswersError):
        await service.finish(user_id, session.id)


@pytest.mark.asyncio
async def test_finish_has_explicit_terminal_and_user_rules() -> None:
    user_id, base_id = uuid4(), uuid4()
    service, repository, _, _ = _service(context=_context())
    session = await service.create_session(**_create_args(user_id, base_id))
    await service.start(user_id, session.id)

    with pytest.raises(InterviewNotFoundError):
        await service.finish(uuid4(), session.id)

    cancelled = _seed_conversation(
        repository, user_id, InterviewStatus.CANCELLED, "cancelled", utc_now()
    )
    failed = _seed_conversation(repository, user_id, InterviewStatus.FAILED, "failed", utc_now())
    with pytest.raises(InvalidInterviewTransitionError):
        await service.finish(user_id, cancelled.id)
    with pytest.raises(InvalidInterviewTransitionError):
        await service.finish(user_id, failed.id)

    _mark_first_turn_completed(repository, session, user_id)
    completed = await service.finish(user_id, session.id)
    assert await service.finish(user_id, completed.id) == completed


@pytest.mark.asyncio
async def test_no_ready_knowledge_marks_session_failed() -> None:
    service, _, _, _ = _service(error=InterviewKnowledgeUnavailableError("empty"))
    session = await service.create_session(**_create_args(uuid4(), uuid4()))
    assert session.status == InterviewStatus.FAILED
    assert session.failure_code == "interview_knowledge_unavailable"


@pytest.mark.asyncio
async def test_conversation_listing_maps_statuses_and_isolates_users() -> None:
    user_id, other_user_id = uuid4(), uuid4()
    service, repository, _, _ = _service(context=_context())
    now = datetime.now(UTC)
    statuses = [
        InterviewStatus.CREATED,
        InterviewStatus.PREPARING,
        InterviewStatus.READY,
        InterviewStatus.IN_PROGRESS,
        InterviewStatus.COMPLETED,
        InterviewStatus.FAILED,
        InterviewStatus.CANCELLED,
    ]
    for index, session_status in enumerate(statuses):
        _seed_conversation(
            repository,
            user_id,
            session_status,
            f"岗位 {index}",
            now - timedelta(minutes=index),
        )
    _seed_conversation(repository, other_user_id, InterviewStatus.READY, "其他用户", now)

    sessions, total = await service.list_conversations(user_id, current=1, size=20)

    assert total == len(statuses)
    assert [session.job_title for session in sessions] == [
        f"岗位 {index}" for index in range(len(statuses))
    ]
    assert [
        {
            InterviewStatus.CREATED: "DRAFT",
            InterviewStatus.PREPARING: "RESUME_UPLOADING",
            InterviewStatus.READY: "READY",
            InterviewStatus.IN_PROGRESS: "IN_PROGRESS",
            InterviewStatus.COMPLETED: "COMPLETED",
            InterviewStatus.FAILED: "FAILED",
            InterviewStatus.CANCELLED: "CANCELLED",
        }[session.status]
        for session in sessions
    ] == [
        "DRAFT",
        "RESUME_UPLOADING",
        "READY",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]


@pytest.mark.asyncio
async def test_conversation_listing_filters_before_pagination() -> None:
    user_id = uuid4()
    service, repository, _, _ = _service(context=_context())
    now = datetime.now(UTC)
    _seed_conversation(repository, user_id, InterviewStatus.CREATED, "Java 工程师", now)
    _seed_conversation(
        repository,
        user_id,
        InterviewStatus.READY,
        "Python 工程师",
        now - timedelta(minutes=1),
    )
    _seed_conversation(
        repository,
        user_id,
        InterviewStatus.COMPLETED,
        "数据分析师",
        now - timedelta(minutes=2),
    )

    drafts, draft_total = await service.list_conversations(
        user_id, status="DRAFT", current=1, size=10
    )
    keyword_matches, keyword_total = await service.list_conversations(
        user_id, keyword="python", current=1, size=1
    )

    assert draft_total == 1
    assert [session.status for session in drafts] == [InterviewStatus.CREATED]
    assert keyword_total == 1
    assert len(keyword_matches) == 1
    assert keyword_matches[0].job_title == "Python 工程师"


def test_conversation_api_contract_and_pagination_validation() -> None:
    user = User(
        id=uuid4(),
        username="conversation-user",
        email="conversation@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    service, repository, _, _ = _service(context=_context())
    now = datetime.now(UTC)
    newest = _seed_conversation(repository, user.id, InterviewStatus.CREATED, "Java", now)
    _seed_conversation(
        repository,
        user.id,
        InterviewStatus.PREPARING,
        "Python",
        now - timedelta(minutes=1),
    )
    _seed_conversation(
        repository,
        uuid4(),
        InterviewStatus.READY,
        "不应返回",
        now + timedelta(minutes=1),
    )

    try:
        with TestClient(app) as client:
            unauthorized = client.get("/api/xunzhi/v1/interview/conversations")
            assert unauthorized.status_code == 401
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_interview_service] = lambda: service

            response = client.get(
                "/api/xunzhi/v1/interview/conversations",
                params={"current": 1, "size": 2},
                headers={"Authorization": "Bearer test"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["total"] == 2
            assert body["current"] == 1
            assert body["size"] == 2
            assert body["pages"] == 1
            assert body["records"] == [
                {
                    "sessionId": str(newest.id),
                    "conversationTitle": "Java",
                    "status": "DRAFT",
                    "interviewType": "TECHNICAL",
                    "resumeFileUrl": None,
                    "createTime": newest.created_at.isoformat().replace("+00:00", "Z"),
                    "updateTime": newest.updated_at.isoformat().replace("+00:00", "Z"),
                },
                {
                    "sessionId": body["records"][1]["sessionId"],
                    "conversationTitle": "Python",
                    "status": "RESUME_UPLOADING",
                    "interviewType": "TECHNICAL",
                    "resumeFileUrl": None,
                    "createTime": body["records"][1]["createTime"],
                    "updateTime": body["records"][1]["updateTime"],
                },
            ]

            assert (
                client.get(
                    "/api/xunzhi/v1/interview/conversations",
                    params={"current": 0},
                    headers={"Authorization": "Bearer test"},
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/xunzhi/v1/interview/conversations",
                    params={"size": 101},
                    headers={"Authorization": "Bearer test"},
                ).status_code
                == 422
            )
    finally:
        app.dependency_overrides.clear()


def test_conversation_api_returns_empty_page() -> None:
    user = User(
        id=uuid4(),
        username="empty-conversation-user",
        email="empty-conversation@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    service, _, _, _ = _service(context=_context())
    try:
        with TestClient(app) as client:
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_interview_service] = lambda: service
            response = client.get(
                "/api/xunzhi/v1/interview/conversations",
                params={"current": 2, "size": 10},
                headers={"Authorization": "Bearer test"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "records": [],
                "total": 0,
                "size": 10,
                "current": 2,
                "pages": 0,
            }
    finally:
        app.dependency_overrides.clear()


def test_interview_api_requires_auth_and_exposes_contract() -> None:
    user = User(
        id=uuid4(),
        username="interview-user",
        email="interview@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    service, _, _, _ = _service(context=_context())
    try:
        with TestClient(app) as client:
            unauthorized = client.get("/api/xunzhi/v1/interview/sessions")
            assert unauthorized.status_code == 401
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_interview_service] = lambda: service
            response = client.post(
                "/api/xunzhi/v1/interview/sessions",
                headers={"Authorization": "Bearer test"},
                json={
                    "knowledgeBaseId": str(uuid4()),
                    "jobTitle": "Python",
                    "jobDescription": "FastAPI",
                    "difficulty": "MEDIUM",
                    "questionCount": 3,
                    "requestId": "api-request",
                },
            )
            assert response.status_code == 201
            body = response.json()
            assert body["status"] == "READY"
            assert body["canStart"] is True
            session_id = body["sessionId"]
            started = client.post(
                f"/api/xunzhi/v1/interview/sessions/{session_id}/start",
                headers={"Authorization": "Bearer test"},
            )
            assert started.status_code == 200
            assert started.json()["status"] == "IN_PROGRESS"
            questions = client.get(
                f"/api/xunzhi/v1/interview/sessions/{session_id}/questions",
                headers={"Authorization": "Bearer test"},
            )
            assert questions.status_code == 200
            assert len(questions.json()) == 1
            assert questions.json()[0]["citations"][0]["sourceId"] == "[S1]"
    finally:
        app.dependency_overrides.clear()


def test_finish_api_completes_active_session_and_rejects_other_user() -> None:
    user = User(
        id=uuid4(),
        username="finish-user",
        email="finish@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    service, repository, _, _ = _service(context=_context())
    session = __import__("asyncio").run(
        service.create_session(**_create_args(user.id, uuid4()))
    )
    __import__("asyncio").run(service.start(user.id, session.id))
    _mark_first_turn_completed(repository, session, user.id)

    try:
        with TestClient(app) as client:
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_interview_service] = lambda: service
            response = client.post(
                f"/api/xunzhi/v1/interview/sessions/{session.id}/finish",
                headers={"Authorization": "Bearer test"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "COMPLETED"

            other_user = User(
                id=uuid4(),
                username="other-finish-user",
                email="other-finish@example.com",
                password_hash="hidden",
                is_active=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            app.dependency_overrides[get_current_user] = lambda: other_user
            forbidden = client.post(
                f"/api/xunzhi/v1/interview/sessions/{session.id}/finish",
                headers={"Authorization": "Bearer test"},
            )
            assert forbidden.status_code == 404
    finally:
        app.dependency_overrides.clear()
