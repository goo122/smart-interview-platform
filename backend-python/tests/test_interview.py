from collections.abc import Awaitable, Callable
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
    TurnStatus,
    TurnType,
    utc_now,
)
from app.modules.interview.exceptions import (
    InterviewKnowledgeUnavailableError,
    InvalidInterviewRequestError,
    InvalidInterviewTransitionError,
)
from app.modules.interview.service import InterviewService
from app.modules.interview.state_machine import InterviewStateMachine
from app.modules.knowledge.context import ContextCitation


class InMemoryInterviewRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, InterviewSession] = {}
        self.questions: dict[UUID, list[InterviewQuestion]] = {}
        self.events: dict[UUID, list[InterviewEvent]] = {}
        self.turns: dict[UUID, list[InterviewTurn]] = {}
        self.answers: dict[UUID, InterviewAnswer] = {}
        self.evaluations: dict[UUID, InterviewEvaluation] = {}

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
async def test_no_ready_knowledge_marks_session_failed() -> None:
    service, _, _, _ = _service(error=InterviewKnowledgeUnavailableError("empty"))
    session = await service.create_session(**_create_args(uuid4(), uuid4()))
    assert session.status == InterviewStatus.FAILED
    assert session.failure_code == "interview_knowledge_unavailable"


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
