import asyncio
import contextlib
import logging
import time
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from arq import Retry
from arq.connections import ArqRedis, RedisSettings
from arq.worker import Worker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.ai.factory import AiProviderFactory
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine, create_session_factory
from app.infrastructure.storage.files import LocalFileStorage
from app.infrastructure.storage.pdf import PypdfPdfParser
from app.infrastructure.vectorstore.retriever import PgVectorRetriever
from app.infrastructure.vectorstore.sqlalchemy import SqlAlchemyVectorStore
from app.modules.auth.models import UserModel  # noqa: F401
from app.modules.interview.context import InterviewContextProvider
from app.modules.interview.domain import InterviewStatus
from app.modules.interview.exceptions import RetryableInterviewPreparationError
from app.modules.interview.repository import SqlAlchemyInterviewRepository
from app.modules.interview.workflow import InterviewPreparationWorkflow
from app.modules.knowledge.context import ContextAssembler
from app.modules.knowledge.domain import utc_now
from app.modules.knowledge.exceptions import RetryableKnowledgeImportError
from app.modules.knowledge.repository import (
    SqlAlchemyKnowledgeRepository,
)
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter
from app.workers.queue import DocumentImportJob, InterviewPreparationJob
from app.workers.redis_queue import (
    DOCUMENT_IMPORT_QUEUE,
    ArqDocumentTaskQueue,
    enqueue_document_job,
    enqueue_interview_preparation_job,
)

logger = logging.getLogger(__name__)
WORKER_HEALTH_KEY = "knowledge-import-worker:health"


async def process_knowledge_document(
    ctx: dict[str, Any],
    *,
    document_id: str,
    user_id: str,
    knowledge_base_id: str,
    request_id: str,
) -> None:
    """Process one document with dependencies owned by the Worker process."""

    settings = cast(Settings, ctx["settings"])
    job_try = int(ctx.get("job_try", 1))
    job = DocumentImportJob(
        document_id=UUID(document_id),
        user_id=UUID(user_id),
        knowledge_base_id=UUID(knowledge_base_id),
        request_id=request_id,
    )
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    async with session_factory() as session:
        service = KnowledgeService(
            SqlAlchemyKnowledgeRepository(session),
            cast(LocalFileStorage, ctx["file_storage"]),
            cast(PypdfPdfParser, ctx["pdf_parser"]),
            cast(SimpleTextSplitter, ctx["text_splitter"]),
            ctx["embedding"],
            SqlAlchemyVectorStore(session, settings.embedding_dimensions),
            cast(ArqDocumentTaskQueue, ctx["document_task_queue"]),
            settings,
        )
        try:
            await service.process_document_job(job, attempt=job_try)
        except RetryableKnowledgeImportError as exc:
            delay = settings.knowledge_task_retry_base_seconds * (2 ** (job_try - 1))
            logger.warning(
                "Knowledge document job deferred",
                extra={
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "request_id": request_id,
                    "attempt": job_try,
                    "provider": settings.embedding_provider,
                    "retry_delay_seconds": delay,
                },
            )
            raise Retry(defer=delay) from exc


async def process_interview_preparation(
    ctx: dict[str, Any],
    *,
    session_id: str,
    user_id: str,
    request_id: str,
) -> None:
    """Prepare one interview using dependencies owned by the Worker process."""

    settings = cast(Settings, ctx["settings"])
    job_try = int(ctx.get("job_try", 1))
    job = InterviewPreparationJob(
        session_id=UUID(session_id),
        user_id=UUID(user_id),
        request_id=request_id,
    )
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    started_at = time.perf_counter()
    async with session_factory() as session:
        repository = SqlAlchemyInterviewRepository(session)
        current = await repository.get_for_user(job.session_id, job.user_id)
        if current is None or current.status != InterviewStatus.PREPARING:
            return
        stale_before = utc_now() - timedelta(
            seconds=settings.interview_preparation_stale_seconds
        )
        claimed = await repository.claim_preparation(
            job.session_id, job.user_id, stale_before, job_try
        )
        if claimed is None:
            return
        if (
            settings.ai_provider == "unavailable"
            or settings.embedding_provider == "unavailable"
        ):
            await repository.mark_failed(
                job.session_id,
                job.user_id,
                "INTERVIEW_PROVIDER_UNAVAILABLE",
                "Interview preparation provider is not configured",
            )
            return
        workflow = InterviewPreparationWorkflow(
            repository,
            InterviewContextProvider(
                SqlAlchemyKnowledgeRepository(session),
                ctx["embedding"],
                PgVectorRetriever(session, settings.embedding_dimensions),
                ContextAssembler(settings.rag_max_context_tokens, settings.rag_max_chunk_tokens),
                settings,
            ),
            ctx["interview_question_generator"],
            ctx["resume_evaluator"],
        )
        common_log = {
            "session_id": session_id,
            "user_id": user_id,
            "request_id": request_id,
            "attempt": job_try,
            "provider": settings.ai_provider,
        }
        logger.info("Interview preparation started", extra=common_log)
        try:
            result = await workflow.prepare(
                job.user_id,
                job.session_id,
                preparation_claimed=True,
                worker_mode=True,
            )
        except RetryableInterviewPreparationError as exc:
            await session.rollback()
            if job_try >= settings.interview_preparation_task_max_attempts:
                await repository.mark_failed(
                    job.session_id,
                    job.user_id,
                    "INTERVIEW_PREPARATION_RETRY_EXHAUSTED",
                    "Interview preparation failed after several attempts",
                )
                logger.warning(
                    "Interview preparation failed after retries",
                    extra={
                        **common_log,
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                        "failure_code": "INTERVIEW_PREPARATION_RETRY_EXHAUSTED",
                    },
                )
                return
            delay = settings.interview_preparation_retry_base_seconds * (2 ** (job_try - 1))
            logger.warning(
                "Interview preparation will retry",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "retry_delay_seconds": delay,
                    "failure_category": type(exc).__name__,
                },
            )
            raise Retry(defer=delay) from exc
        logger.info(
            "Interview preparation completed",
            extra={
                **common_log,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "status": result.status.value,
            },
        )


async def worker_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    providers = AiProviderFactory.build(settings)
    if settings.embedding_provider != "unavailable":
        await AiProviderFactory.validate_embedding_dimensions(
            providers.embedding,
            settings.embedding_dimensions,
        )
    engine = create_database_engine(str(settings.database_url))
    ctx["settings"] = settings
    ctx["session_factory"] = create_session_factory(engine)
    ctx["engine"] = engine
    ctx["embedding"] = providers.embedding
    ctx["interview_question_generator"] = providers.interview_question_generator
    ctx["resume_evaluator"] = providers.resume_evaluator
    ctx["file_storage"] = LocalFileStorage(settings.knowledge_storage_dir)
    ctx["pdf_parser"] = PypdfPdfParser()
    ctx["text_splitter"] = SimpleTextSplitter(
        settings.rag_chunk_size,
        settings.rag_chunk_overlap,
    )
    ctx["document_task_queue"] = ArqDocumentTaskQueue.create(str(settings.redis_url))
    await _recover_stale_documents(ctx)
    await _recover_interview_preparations(ctx)
    ctx["interview_recovery_task"] = asyncio.create_task(
        _interview_preparation_recovery_loop(ctx),
        name="interview-preparation-recovery",
    )


async def worker_shutdown(ctx: dict[str, Any]) -> None:
    recovery_task = cast(asyncio.Task[None] | None, ctx.pop("interview_recovery_task", None))
    if recovery_task is not None:
        recovery_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await recovery_task
    engine = cast(AsyncEngine | None, ctx.pop("engine", None))
    document_task_queue = cast(
        ArqDocumentTaskQueue | None,
        ctx.pop("document_task_queue", None),
    )
    if document_task_queue is not None:
        await document_task_queue.close()
    if engine is not None:
        await engine.dispose()


async def _recover_interview_preparations(ctx: dict[str, Any]) -> None:
    settings = cast(Settings, ctx["settings"])
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    redis = cast(ArqRedis, ctx["redis"])
    stale_before = utc_now() - timedelta(
        seconds=settings.interview_preparation_stale_seconds
    )
    async with session_factory() as session:
        repository = SqlAlchemyInterviewRepository(session)
        recoverable = await repository.list_recoverable_preparations(
            stale_before,
            settings.interview_preparation_recovery_batch_size,
        )
    for interview in recoverable:
        job = InterviewPreparationJob(
            session_id=interview.id,
            user_id=interview.user_id,
            request_id=f"recovery:{interview.id}",
            job_id=(
                f"interview-preparation:{interview.id}:recovery:"
                f"{interview.preparation_attempt_count}"
            ),
        )
        await enqueue_interview_preparation_job(redis, job)
        logger.info(
            "Recovered interview preparation job",
            extra={
                "session_id": str(interview.id),
                "user_id": str(interview.user_id),
                "request_id": job.request_id,
                "attempt": interview.preparation_attempt_count,
                "provider": settings.ai_provider,
            },
        )


async def _interview_preparation_recovery_loop(ctx: dict[str, Any]) -> None:
    settings = cast(Settings, ctx["settings"])
    while True:
        await asyncio.sleep(settings.interview_preparation_recovery_interval_seconds)
        try:
            await _recover_interview_preparations(ctx)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Interview preparation recovery failed")


async def _recover_stale_documents(ctx: dict[str, Any]) -> None:
    settings = cast(Settings, ctx["settings"])
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    redis = cast(ArqRedis, ctx["redis"])
    stale_before = utc_now() - timedelta(
        seconds=settings.knowledge_processing_stale_seconds
    )
    async with session_factory() as session:
        repository = SqlAlchemyKnowledgeRepository(session)
        recoverable = await repository.list_recoverable_documents(stale_before)
    for document, user_id in recoverable:
        job = DocumentImportJob(
            document_id=document.id,
            user_id=user_id,
            knowledge_base_id=document.knowledge_base_id,
            request_id=f"recovery:{document.id}",
        )
        await enqueue_document_job(redis, job)
        logger.info(
            "Recovered knowledge document job",
            extra={
                "document_id": str(document.id),
                "knowledge_base_id": str(document.knowledge_base_id),
                "request_id": job.request_id,
                "attempt": document.attempt_count,
                "provider": settings.embedding_provider,
            },
        )


def create_worker() -> Worker:
    settings = get_settings()
    return Worker(
        functions=[process_knowledge_document, process_interview_preparation],
        queue_name=DOCUMENT_IMPORT_QUEUE,
        redis_settings=RedisSettings.from_dsn(str(settings.redis_url)),
        on_startup=worker_startup,
        on_shutdown=worker_shutdown,
        max_jobs=4,
        job_timeout=max(
            settings.knowledge_task_timeout_seconds,
            settings.interview_preparation_task_timeout_seconds,
        ),
        max_tries=max(
            settings.knowledge_task_max_attempts,
            settings.interview_preparation_task_max_attempts,
        ),
        retry_jobs=True,
        health_check_interval=15,
        health_check_key=WORKER_HEALTH_KEY,
        log_results=False,
    )


if __name__ == "__main__":
    create_worker().run()
