import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.workers.queue import (
    DocumentImportHandler,
    DocumentImportJob,
    InterviewAnswerEvaluationJob,
    InterviewPreparationJob,
    InterviewReportGenerationJob,
)

DOCUMENT_IMPORT_FUNCTION = "process_knowledge_document"
INTERVIEW_PREPARATION_FUNCTION = "process_interview_preparation"
INTERVIEW_ANSWER_EVALUATION_FUNCTION = "process_interview_answer_evaluation"
INTERVIEW_REPORT_GENERATION_FUNCTION = "process_interview_report_generation"
DOCUMENT_IMPORT_QUEUE = "knowledge:documents"


class ArqDocumentTaskQueue:
    """ARQ-backed queue for serializable knowledge-document jobs."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: ArqRedis | None = None
        self._redis_lock = asyncio.Lock()

    @classmethod
    def create(cls, redis_url: str) -> "ArqDocumentTaskQueue":
        return cls(redis_url)

    async def _get_redis(self) -> ArqRedis:
        if self._redis is None:
            async with self._redis_lock:
                if self._redis is None:
                    self._redis = await create_pool(
                        RedisSettings.from_dsn(self._redis_url),
                        default_queue_name=DOCUMENT_IMPORT_QUEUE,
                    )
        return self._redis

    async def enqueue_document(self, job: DocumentImportJob) -> None:
        redis = await self._get_redis()
        await enqueue_document_job(redis, job)

    async def enqueue_interview_preparation(self, job: InterviewPreparationJob) -> None:
        redis = await self._get_redis()
        await enqueue_interview_preparation_job(redis, job)

    async def enqueue_interview_answer_evaluation(
        self, job: InterviewAnswerEvaluationJob
    ) -> None:
        redis = await self._get_redis()
        await enqueue_interview_answer_evaluation_job(redis, job)

    async def enqueue_interview_report(
        self, job: InterviewReportGenerationJob
    ) -> None:
        redis = await self._get_redis()
        await enqueue_interview_report_job(redis, job)

    def bind_inline_handler(self, handler: DocumentImportHandler) -> None:
        del handler

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose(close_connection_pool=True)
            self._redis = None


class ArqInterviewTaskQueue(ArqDocumentTaskQueue):
    """ARQ queue facade for interview jobs sharing the Worker queue."""


async def enqueue_document_job(redis: ArqRedis, job: DocumentImportJob) -> None:
    """Enqueue a document job with a deterministic ARQ job ID."""

    await redis.enqueue_job(
        DOCUMENT_IMPORT_FUNCTION,
        document_id=str(job.document_id),
        user_id=str(job.user_id),
        knowledge_base_id=str(job.knowledge_base_id),
        request_id=job.request_id,
        _job_id=f"knowledge-document:{job.document_id}",
        _queue_name=DOCUMENT_IMPORT_QUEUE,
    )


async def enqueue_interview_preparation_job(
    redis: ArqRedis, job: InterviewPreparationJob
) -> None:
    """Enqueue preparation with a deterministic ARQ job ID."""

    await redis.enqueue_job(
        INTERVIEW_PREPARATION_FUNCTION,
        session_id=str(job.session_id),
        user_id=str(job.user_id),
        request_id=job.request_id,
        _job_id=job.job_id or f"interview-preparation:{job.session_id}",
        _queue_name=DOCUMENT_IMPORT_QUEUE,
    )


async def enqueue_interview_answer_evaluation_job(
    redis: ArqRedis, job: InterviewAnswerEvaluationJob
) -> None:
    """Enqueue answer evaluation with a deterministic, attempt-aware ARQ ID."""

    await redis.enqueue_job(
        INTERVIEW_ANSWER_EVALUATION_FUNCTION,
        user_id=str(job.user_id),
        session_id=str(job.session_id),
        turn_id=str(job.turn_id),
        answer_id=str(job.answer_id),
        request_id=job.request_id,
        _job_id=job.job_id or f"interview-answer-evaluation:{job.turn_id}",
        _queue_name=DOCUMENT_IMPORT_QUEUE,
    )


async def enqueue_interview_report_job(
    redis: ArqRedis, job: InterviewReportGenerationJob
) -> None:
    """Enqueue a report task with a stable ID for normal requests and recovery IDs."""

    await redis.enqueue_job(
        INTERVIEW_REPORT_GENERATION_FUNCTION,
        report_id=str(job.report_id),
        session_id=str(job.session_id),
        user_id=str(job.user_id),
        request_id=job.request_id,
        _job_id=job.job_id or f"interview-report-generation:{job.report_id}",
        _queue_name=DOCUMENT_IMPORT_QUEUE,
    )
