from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.interview.domain import InterviewSession, InterviewStatus
from app.workers import worker as worker_module
from app.workers.queue import (
    InterviewAnswerEvaluationJob,
    InterviewPreparationJob,
    InterviewReportGenerationJob,
    InterviewResumeEvaluationJob,
)
from app.workers.redis_queue import (
    INTERVIEW_ANSWER_EVALUATION_FUNCTION,
    INTERVIEW_PREPARATION_FUNCTION,
    INTERVIEW_REPORT_GENERATION_FUNCTION,
    INTERVIEW_RESUME_EVALUATION_FUNCTION,
    enqueue_interview_answer_evaluation_job,
    enqueue_interview_preparation_job,
    enqueue_interview_report_job,
    enqueue_interview_resume_evaluation_job,
)
from app.workers.worker import worker_shutdown


def test_queue_wait_ms_uses_arq_enqueue_time() -> None:
    enqueue_time = datetime.now(UTC) - timedelta(seconds=2)

    result = worker_module._queue_wait_ms({"enqueue_time": enqueue_time})

    assert result is not None
    assert 1_900 <= result <= 3_000


def test_queue_wait_ms_is_optional_outside_arq() -> None:
    assert worker_module._queue_wait_ms({}) is None


class RecordingQueue:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class RecordingEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class RecordingRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def enqueue_job(self, function_name: str, **kwargs: object) -> None:
        self.calls.append((function_name, kwargs))


@pytest.mark.asyncio
async def test_interview_preparation_job_has_serializable_deterministic_payload() -> None:
    redis = RecordingRedis()
    job = InterviewPreparationJob(uuid4(), uuid4(), "request-1")

    await enqueue_interview_preparation_job(redis, job)  # type: ignore[arg-type]

    assert redis.calls == [
        (
            INTERVIEW_PREPARATION_FUNCTION,
            {
                "session_id": str(job.session_id),
                "user_id": str(job.user_id),
                "request_id": "request-1",
                "_job_id": f"interview-preparation:{job.session_id}",
                "_queue_name": "knowledge:documents",
            },
        )
    ]


@pytest.mark.asyncio
async def test_recovery_job_can_use_a_deterministic_attempt_specific_id() -> None:
    redis = RecordingRedis()
    job = InterviewPreparationJob(
        uuid4(), uuid4(), "recovery-request", "interview-preparation:session:recovery:2"
    )

    await enqueue_interview_preparation_job(redis, job)  # type: ignore[arg-type]

    assert redis.calls[0][1]["_job_id"] == job.job_id


@pytest.mark.asyncio
async def test_resume_evaluation_job_has_only_serializable_identifiers() -> None:
    redis = RecordingRedis()
    job = InterviewResumeEvaluationJob(uuid4(), uuid4(), "resume-evaluation-1")

    await enqueue_interview_resume_evaluation_job(redis, job)  # type: ignore[arg-type]

    assert redis.calls == [
        (
            INTERVIEW_RESUME_EVALUATION_FUNCTION,
            {
                "session_id": str(job.session_id),
                "user_id": str(job.user_id),
                "request_id": job.request_id,
                "_job_id": f"interview-resume-evaluation:{job.session_id}",
                "_queue_name": "knowledge:documents",
            },
        )
    ]


@pytest.mark.asyncio
async def test_answer_evaluation_job_has_only_serializable_identifiers() -> None:
    redis = RecordingRedis()
    job = InterviewAnswerEvaluationJob(uuid4(), uuid4(), uuid4(), uuid4(), "answer-1")

    await enqueue_interview_answer_evaluation_job(redis, job)  # type: ignore[arg-type]

    assert redis.calls == [
        (
            INTERVIEW_ANSWER_EVALUATION_FUNCTION,
            {
                "user_id": str(job.user_id),
                "session_id": str(job.session_id),
                "turn_id": str(job.turn_id),
                "answer_id": str(job.answer_id),
                "request_id": job.request_id,
                "_job_id": f"interview-answer-evaluation:{job.turn_id}",
                "_queue_name": "knowledge:documents",
            },
        )
    ]


@pytest.mark.asyncio
async def test_report_generation_job_has_only_serializable_identifiers() -> None:
    redis = RecordingRedis()
    job = InterviewReportGenerationJob(uuid4(), uuid4(), uuid4(), "report-1")

    await enqueue_interview_report_job(redis, job)  # type: ignore[arg-type]

    assert redis.calls == [
        (
            INTERVIEW_REPORT_GENERATION_FUNCTION,
            {
                "report_id": str(job.report_id),
                "session_id": str(job.session_id),
                "user_id": str(job.user_id),
                "request_id": job.request_id,
                "_job_id": f"interview-report-generation:{job.report_id}",
                "_queue_name": "knowledge:documents",
            },
        )
    ]


@pytest.mark.asyncio
async def test_worker_shutdown_releases_queue_and_database_resources() -> None:
    queue = RecordingQueue()
    engine = RecordingEngine()
    context = {"document_task_queue": queue, "engine": engine}

    await worker_shutdown(context)  # type: ignore[arg-type]

    assert queue.closed
    assert engine.disposed
    assert context == {}


@pytest.mark.asyncio
async def test_preparation_and_resume_evaluation_use_different_database_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        def __init__(self, value: object) -> None:
            self.value = value

        async def __aenter__(self) -> object:
            return self.value

        async def __aexit__(self, *_args: object) -> None:
            return None

    class SessionFactory:
        def __init__(self) -> None:
            self.sessions: list[object] = []

        def __call__(self) -> SessionContext:
            value = object()
            self.sessions.append(value)
            return SessionContext(value)

    session_factory = SessionFactory()
    session = InterviewSession.new(
        user_id=uuid4(),
        knowledge_base_id=uuid4(),
        job_title="Python 工程师",
        job_description="负责后端系统设计",
        interview_type="TECHNICAL",
        difficulty="MEDIUM",
        question_count=5,
        request_id="worker-session-isolation",
    )
    session.status = InterviewStatus.PREPARING
    repository_sessions: list[object] = []

    class Repository:
        def __init__(self, value: object) -> None:
            repository_sessions.append(value)

        async def get_for_user(self, _session_id: object, _user_id: object):
            return session

        async def claim_preparation(self, *_args: object, **_kwargs: object):
            return session

        async def list_questions(self, _session_id: object):
            return []

    class PreparationWorkflow:
        timings = {
            "context_retrieval_ms": 1.0,
            "question_generation_ms": 2.0,
            "database_storage_ms": 3.0,
        }

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def prepare(self, *_args: object, **_kwargs: object):
            return session

    class ResumeEvaluationWorkflow:
        timings: dict[str, float] = {}

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def evaluate(self, *_args: object, **_kwargs: object):
            return None

    monkeypatch.setattr(worker_module, "SqlAlchemyInterviewRepository", Repository)
    monkeypatch.setattr(worker_module, "InterviewPreparationWorkflow", PreparationWorkflow)
    monkeypatch.setattr(
        worker_module, "InterviewResumeEvaluationWorkflow", ResumeEvaluationWorkflow
    )
    settings = Settings(_env_file=None, ai_provider="fake", embedding_provider="fake")
    context = {
        "settings": settings,
        "session_factory": session_factory,
        "embedding": object(),
        "interview_question_generator": object(),
        "resume_evaluator": object(),
        "resume_role_inference": object(),
        "document_task_queue": object(),
    }

    await worker_module.process_interview_preparation(
        context,
        session_id=str(session.id),
        user_id=str(session.user_id),
        request_id="preparation-job",
    )
    await worker_module.process_interview_resume_evaluation(
        context,
        session_id=str(session.id),
        user_id=str(session.user_id),
        request_id="resume-evaluation-job",
    )

    assert len(session_factory.sessions) == 2
    assert repository_sessions == session_factory.sessions
    assert repository_sessions[0] is not repository_sessions[1]
