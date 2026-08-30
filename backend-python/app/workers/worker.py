import logging
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
from app.infrastructure.vectorstore.sqlalchemy import SqlAlchemyVectorStore
from app.modules.knowledge.domain import utc_now
from app.modules.knowledge.exceptions import RetryableKnowledgeImportError
from app.modules.knowledge.repository import (
    SqlAlchemyKnowledgeRepository,
)
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter
from app.workers.queue import DocumentImportJob
from app.workers.redis_queue import (
    DOCUMENT_IMPORT_QUEUE,
    ArqDocumentTaskQueue,
    enqueue_document_job,
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
    ctx["file_storage"] = LocalFileStorage(settings.knowledge_storage_dir)
    ctx["pdf_parser"] = PypdfPdfParser()
    ctx["text_splitter"] = SimpleTextSplitter(
        settings.rag_chunk_size,
        settings.rag_chunk_overlap,
    )
    ctx["document_task_queue"] = ArqDocumentTaskQueue.create(str(settings.redis_url))
    await _recover_stale_documents(ctx)


async def worker_shutdown(ctx: dict[str, Any]) -> None:
    engine = cast(AsyncEngine | None, ctx.pop("engine", None))
    document_task_queue = cast(
        ArqDocumentTaskQueue | None,
        ctx.pop("document_task_queue", None),
    )
    if document_task_queue is not None:
        await document_task_queue.close()
    if engine is not None:
        await engine.dispose()


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
        functions=[process_knowledge_document],
        queue_name=DOCUMENT_IMPORT_QUEUE,
        redis_settings=RedisSettings.from_dsn(str(settings.redis_url)),
        on_startup=worker_startup,
        on_shutdown=worker_shutdown,
        max_jobs=4,
        job_timeout=settings.knowledge_task_timeout_seconds,
        max_tries=settings.knowledge_task_max_attempts,
        retry_jobs=True,
        health_check_interval=15,
        health_check_key=WORKER_HEALTH_KEY,
        log_results=False,
    )


if __name__ == "__main__":
    create_worker().run()
