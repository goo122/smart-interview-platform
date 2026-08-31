import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_interview import FakeTaskQueue, InMemoryInterviewRepository

from app.ai.evaluation import FakeInterviewAnswerEvaluator, StructuredInterviewEvaluation
from app.ai.followup import FakeFollowUpQuestionGenerator, GeneratedFollowUpQuestion
from app.core.config import Settings
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.interview.answer_service import InterviewAnswerService
from app.modules.interview.context import InterviewEvaluationContext
from app.modules.interview.dependencies import get_interview_answer_service
from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewQuestion,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    TurnStatus,
    utc_now,
)
from app.modules.interview.exceptions import (
    InterviewAnswerConflictError,
    InterviewAnswerError,
    InterviewEvaluationQueueUnavailableError,
    InterviewNotFoundError,
)
from app.modules.interview.follow_up import FollowUpPolicy
from app.workers.queue import InterviewAnswerEvaluationJob


class FakeEvaluationContextProvider:
    async def build(self, **_kwargs: object) -> InterviewEvaluationContext:
        return InterviewEvaluationContext(prompt="safe context", citations=())


class InvalidThenValidEvaluator:
    def __init__(self) -> None:
        self.calls = 0

    async def evaluate(self, _request: object) -> object:
        self.calls += 1
        if self.calls == 1:
            return {"overall_score": 101}
        return _evaluation(score=90, follow_up=False)


class DeferredAnswerEvaluationQueue:
    def __init__(self, error: Exception | None = None) -> None:
        self.jobs: list[InterviewAnswerEvaluationJob] = []
        self.error = error

    async def enqueue_interview_answer_evaluation(
        self, job: InterviewAnswerEvaluationJob
    ) -> None:
        if self.error is not None:
            raise self.error
        self.jobs.append(job)


def _evaluation(*, score: int = 50, follow_up: bool = True) -> StructuredInterviewEvaluation:
    return StructuredInterviewEvaluation(
        overall_score=score,
        technical_score=score,
        relevance_score=score,
        clarity_score=score,
        depth_score=score,
        strengths=["结构清晰"],
        weaknesses=["缺少量化结果"],
        feedback="回答已完成结构化评估。",
        suggested_improvements=["补充指标"],
        should_follow_up=follow_up,
        follow_up_focus="澄清技术方案",
    )


async def _started_service(
    *,
    evaluator: FakeInterviewAnswerEvaluator | None = None,
    queue: FakeTaskQueue | None = None,
    settings: Settings | None = None,
) -> tuple[InterviewAnswerService, InMemoryInterviewRepository, UUID, UUID, FakeTaskQueue]:
    repository = InMemoryInterviewRepository()
    user_id, base_id = uuid4(), uuid4()
    session = InterviewSession.new(
        user_id=user_id,
        knowledge_base_id=base_id,
        job_title="Python 工程师",
        job_description="负责后端系统开发",
        interview_type=InterviewType.TECHNICAL,
        difficulty=InterviewDifficulty.MEDIUM,
        question_count=2,
        request_id=None,
    )
    session.status = InterviewStatus.READY
    await repository.create(session)
    repository.questions[session.id] = [
        InterviewQuestion(
            id=uuid4(),
            session_id=session.id,
            sequence=index,
            content=f"请说明你的项目方案（第 {index} 题）",
            category="TECHNICAL",
            difficulty=InterviewDifficulty.MEDIUM,
            expected_points=["方案", "结果"],
            source_summary=None,
            created_at=utc_now(),
        )
        for index in (1, 2)
    ]
    await repository.start(session.id, user_id)
    actual_queue = queue or FakeTaskQueue(run_immediately=False)
    service = InterviewAnswerService(
        repository,
        FakeEvaluationContextProvider(),
        evaluator or FakeInterviewAnswerEvaluator(output=_evaluation()),
        FakeFollowUpQuestionGenerator(),
        actual_queue,
        settings or Settings(),
    )
    return service, repository, user_id, session.id, actual_queue


@pytest.mark.asyncio
async def test_start_creates_first_waiting_turn_and_current_turn() -> None:
    service, repository, user_id, session_id, _ = await _started_service()
    current = await service.current_turn(user_id, session_id)
    assert current.turn.sequence == 1
    assert current.turn.status == TurnStatus.WAITING_ANSWER
    assert current.turn.question_id == repository.questions[session_id][0].id


@pytest.mark.asyncio
async def test_submit_answer_is_idempotent_and_only_one_answer_is_saved() -> None:
    service, repository, user_id, session_id, queue = await _started_service()
    turn = await service.current_turn(user_id, session_id)
    first = await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我设计了异步服务并通过指标验证结果。",
        request_id="answer-1",
    )
    repeated = await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我设计了异步服务并通过指标验证结果。",
        request_id="answer-1",
    )
    assert first.answer and repeated.answer
    assert first.answer.id == repeated.answer.id
    assert len(repository.answers) == 1
    assert len(queue.tasks) == 1


@pytest.mark.asyncio
async def test_arq_answer_submission_returns_without_calling_evaluator() -> None:
    queue = DeferredAnswerEvaluationQueue()
    service, repository, user_id, session_id, _ = await _started_service(  # type: ignore[arg-type]
        queue=queue  # type: ignore[arg-type]
    )
    turn = await service.current_turn(user_id, session_id)

    progress = await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我设计了异步服务并通过指标验证结果。",
        request_id="arq-answer-1",
    )

    assert progress.turn.status == TurnStatus.EVALUATING
    assert len(queue.jobs) == 1
    assert repository.sessions[session_id].status == InterviewStatus.IN_PROGRESS
    assert isinstance(service._workflow._evaluator, FakeInterviewAnswerEvaluator)
    assert service._workflow._evaluator.calls == 0  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_arq_enqueue_failure_keeps_answer_recoverable() -> None:
    queue = DeferredAnswerEvaluationQueue(RuntimeError("redis down"))
    service, repository, user_id, session_id, _ = await _started_service(  # type: ignore[arg-type]
        queue=queue  # type: ignore[arg-type]
    )
    turn = await service.current_turn(user_id, session_id)

    with pytest.raises(InterviewEvaluationQueueUnavailableError):
        await service.submit_answer(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn.turn.id,
            answer="我设计了异步服务并通过指标验证结果。",
            request_id="arq-answer-queue-failure",
        )

    assert repository.turns[session_id][0].status == TurnStatus.EVALUATING
    assert repository.sessions[session_id].status == InterviewStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_early_finish_skips_pending_evaluation_after_a_completed_answer() -> None:
    service, repository, user_id, session_id, queue = await _started_service(
        evaluator=FakeInterviewAnswerEvaluator(output=_evaluation(follow_up=False))
    )
    first_turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=first_turn.turn.id,
        answer="我完成了第一个方案并验证了效果。",
        request_id="early-finish-first",
    )
    await queue.tasks.pop(0)()
    second_turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=second_turn.turn.id,
        answer="我已经提交了第二题的回答，等待评分。",
        request_id="early-finish-pending",
    )

    finished = await repository.finish(session_id, user_id)

    assert finished.status == InterviewStatus.COMPLETED
    assert repository.answers[second_turn.turn.id].content.startswith("我已经提交")
    assert second_turn.turn.status == TurnStatus.SKIPPED
    await queue.tasks.pop(0)()
    assert repository.sessions[session_id].status == InterviewStatus.COMPLETED


@pytest.mark.asyncio
async def test_answer_validation_rejects_empty_short_and_long_answers() -> None:
    service, _, user_id, session_id, _ = await _started_service(
        settings=Settings(interview_min_answer_length=3, interview_max_answer_length=20)
    )
    turn = await service.current_turn(user_id, session_id)
    with pytest.raises(InterviewAnswerError):
        await service.submit_answer(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn.turn.id,
            answer=" ",
            request_id="short",
        )
    with pytest.raises(InterviewAnswerError):
        await service.submit_answer(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn.turn.id,
            answer="x" * 21,
            request_id="long",
        )


@pytest.mark.asyncio
async def test_follow_up_policy_is_deterministic_and_limits_depth() -> None:
    policy = FollowUpPolicy(2, 70, 5, 10)
    assert policy.decide(
        _evaluation(score=50), follow_up_depth=0, follow_up_count=0, answer_length=20
    ).should_follow_up
    decision = policy.decide(
        _evaluation(score=50), follow_up_depth=2, follow_up_count=0, answer_length=20
    )
    assert decision.should_follow_up is False
    assert decision.reason == "max_follow_up_depth_reached"
    assert policy.decide(
        _evaluation(score=90), follow_up_depth=0, follow_up_count=0, answer_length=20
    ).should_follow_up is False
    assert policy.decide(
        _evaluation(score=50), follow_up_depth=0, follow_up_count=0, answer_length=0
    ).reason == "answer_length_out_of_range"
    assert policy.decide(
        _evaluation(score=50),
        follow_up_depth=0,
        follow_up_count=0,
        answer_length=20,
        has_next_question=False,
    ).reason == "final_question_needs_clarification"


@pytest.mark.asyncio
async def test_duplicate_start_does_not_create_duplicate_turn() -> None:
    service, repository, user_id, session_id, _ = await _started_service()
    del service
    await repository.start(session_id, user_id)
    assert len(repository.turns[session_id]) == 1


@pytest.mark.asyncio
async def test_other_user_and_completed_turn_cannot_submit() -> None:
    service, repository, user_id, session_id, queue = await _started_service()
    turn = await service.current_turn(user_id, session_id)
    with pytest.raises(InterviewNotFoundError):
        await service.submit_answer(
            user_id=uuid4(),
            session_id=session_id,
            turn_id=turn.turn.id,
            answer="这是一个不应被接受的回答。",
            request_id="other-user",
        )
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我完成了方案设计并验证了结果。",
        request_id="completed-turn",
    )
    await queue.tasks.pop(0)()
    with pytest.raises(InterviewAnswerConflictError):
        await service.submit_answer(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn.turn.id,
            answer="再次提交相同轮次的回答。",
            request_id="completed-turn-2",
        )
    assert repository.turns[session_id][0].status == TurnStatus.COMPLETED


@pytest.mark.asyncio
async def test_invalid_evaluation_output_retries_once() -> None:
    evaluator = InvalidThenValidEvaluator()
    service, repository, user_id, session_id, queue = await _started_service(evaluator=evaluator)  # type: ignore[arg-type]
    turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我给出了完整实现并通过指标验证效果。",
        request_id="invalid-then-valid",
    )
    await queue.tasks.pop(0)()
    assert evaluator.calls == 2
    assert (await service.get_turn(user_id, turn.turn.id)).evaluation is not None
    assert repository.sessions[session_id].status == InterviewStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_invalid_evaluation_output_after_retry_fails_safely() -> None:
    evaluator = FakeInterviewAnswerEvaluator(output={"overall_score": 101})  # type: ignore[arg-type]
    service, repository, user_id, session_id, queue = await _started_service(evaluator=evaluator)
    turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我给出了完整实现并通过指标验证效果。",
        request_id="invalid-twice",
    )
    await queue.tasks.pop(0)()
    assert evaluator.calls == 2
    assert repository.sessions[session_id].status == InterviewStatus.FAILED
    assert repository.evaluations == {}


@pytest.mark.asyncio
async def test_policy_false_does_not_call_follow_up_generator() -> None:
    evaluator = FakeInterviewAnswerEvaluator(output=_evaluation(score=90, follow_up=True))
    service, _, user_id, session_id, queue = await _started_service(evaluator=evaluator)
    generator = service._workflow._follow_up_generator
    assert isinstance(generator, FakeFollowUpQuestionGenerator)
    turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我给出了完整实现并通过指标验证效果。",
        request_id="no-follow-up-generator",
    )
    await queue.tasks.pop(0)()
    assert generator.calls == 0


@pytest.mark.asyncio
async def test_duplicate_follow_up_question_fails_without_leaking_details() -> None:
    evaluator = FakeInterviewAnswerEvaluator(output=_evaluation(score=40, follow_up=True))
    duplicate = GeneratedFollowUpQuestion(
        content="请说明你的项目方案（第 1 题）",
        reason="重复问题",
        expected_points=["方案"],
    )
    service, repository, user_id, session_id, queue = await _started_service(evaluator=evaluator)
    service._workflow._follow_up_generator = FakeFollowUpQuestionGenerator(output=duplicate)
    turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我给出了完整实现并通过指标验证效果。",
        request_id="duplicate-follow-up",
    )
    await queue.tasks.pop(0)()
    assert repository.sessions[session_id].status == InterviewStatus.FAILED
    assert repository.sessions[session_id].failure_code == "interview_evaluation_invalid"


@pytest.mark.asyncio
async def test_cancelled_evaluation_marks_turn_failed_and_cancels_fake_model() -> None:
    evaluator = FakeInterviewAnswerEvaluator(
        output=_evaluation(score=40, follow_up=False), delay_seconds=1
    )
    service, repository, user_id, session_id, queue = await _started_service(evaluator=evaluator)
    turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我给出了完整实现并通过指标验证效果。",
        request_id="cancelled-evaluation",
    )
    task = asyncio.create_task(queue.tasks.pop(0)())
    for _ in range(20):
        if evaluator.calls:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert evaluator.cancelled is True
    assert repository.sessions[session_id].status == InterviewStatus.FAILED


@pytest.mark.asyncio
async def test_scoring_creates_follow_up_then_advances_and_completes() -> None:
    evaluator = FakeInterviewAnswerEvaluator(output=_evaluation(score=50, follow_up=True))
    service, repository, user_id, session_id, queue = await _started_service(evaluator=evaluator)
    first = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=first.turn.id,
        answer="我负责架构设计并通过监控验证了效果。",
        request_id="answer-1",
    )
    await queue.tasks.pop(0)()
    follow_up = await service.current_turn(user_id, session_id)
    assert follow_up.turn.turn_type.value == "FOLLOW_UP"
    assert follow_up.evaluation is None
    assert evaluator.calls == 1

    evaluator.output = _evaluation(score=90, follow_up=False)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=follow_up.turn.id,
        answer="我补充了取舍、边界和上线后的量化结果。",
        request_id="answer-2",
    )
    await queue.tasks.pop(0)()
    next_turn = await service.current_turn(user_id, session_id)
    assert next_turn.turn.sequence == 3
    assert next_turn.turn.question_id == repository.questions[session_id][1].id

    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=next_turn.turn.id,
        answer="我实现了第二个方案并完成了性能复盘。",
        request_id="answer-3",
    )
    await queue.tasks.pop(0)()
    assert (await service.get_turn(user_id, next_turn.turn.id)).evaluation is not None
    assert repository.sessions[session_id].status == InterviewStatus.COMPLETED
    assert all(turn.status == TurnStatus.COMPLETED for turn in repository.turns[session_id])


@pytest.mark.asyncio
async def test_evaluation_failure_marks_turn_and_session_failed() -> None:
    evaluator = FakeInterviewAnswerEvaluator(error=RuntimeError("provider unavailable"))
    service, repository, user_id, session_id, queue = await _started_service(evaluator=evaluator)
    turn = await service.current_turn(user_id, session_id)
    await service.submit_answer(
        user_id=user_id,
        session_id=session_id,
        turn_id=turn.turn.id,
        answer="我给出了完整的技术实现和验证过程。",
        request_id="answer-fail",
    )
    await queue.tasks.pop(0)()
    assert repository.sessions[session_id].status == InterviewStatus.FAILED
    assert repository.turns[session_id][0].status == TurnStatus.FAILED
    assert repository.evaluations == {}


def test_answer_api_requires_auth_and_returns_contract() -> None:
    service, _, user_id, session_id, _ = __import__("asyncio").run(_started_service())
    user = User(
        id=user_id,
        username="answer-user",
        email="answer@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    try:
        with TestClient(app) as client:
            assert client.get(
                f"/api/xunzhi/v1/interview/sessions/{session_id}/current-turn"
            ).status_code == 401
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_interview_answer_service] = lambda: service
            current = client.get(
                f"/api/xunzhi/v1/interview/sessions/{session_id}/current-turn",
                headers={"Authorization": "Bearer test"},
            )
            assert current.status_code == 200
            assert current.json()["status"] == "WAITING_ANSWER"
            turn_id = current.json()["turnId"]
            response = client.post(
                f"/api/xunzhi/v1/interview/sessions/{session_id}/answers",
                headers={"Authorization": "Bearer test"},
                json={
                    "turnId": turn_id,
                    "answer": "我设计了异步服务并完成了上线验证。",
                    "requestId": "api-answer-1",
                },
            )
            assert response.status_code == 202
            assert response.json()["status"] == "EVALUATING"
    finally:
        app.dependency_overrides.clear()
