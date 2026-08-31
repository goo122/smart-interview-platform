from uuid import uuid4

import pytest

from app.workers.queue import (
    InterviewAnswerEvaluationJob,
    InterviewPreparationJob,
    InterviewReportGenerationJob,
)
from app.workers.redis_queue import (
    INTERVIEW_ANSWER_EVALUATION_FUNCTION,
    INTERVIEW_PREPARATION_FUNCTION,
    INTERVIEW_REPORT_GENERATION_FUNCTION,
    enqueue_interview_answer_evaluation_job,
    enqueue_interview_preparation_job,
    enqueue_interview_report_job,
)
from app.workers.worker import worker_shutdown


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
