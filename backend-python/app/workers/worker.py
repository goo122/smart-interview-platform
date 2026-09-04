import asyncio
import contextlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from arq import Retry
from arq.connections import ArqRedis, RedisSettings
from arq.worker import Worker
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.ai.factory import AiProviderFactory
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.exceptions import AppError
from app.infrastructure.storage.files import LocalFileStorage
from app.infrastructure.storage.pdf import PypdfPdfParser
from app.infrastructure.vectorstore.retriever import PgVectorRetriever
from app.infrastructure.vectorstore.sqlalchemy import SqlAlchemyVectorStore
from app.modules.auth.models import UserModel  # noqa: F401
from app.modules.interview.answer_workflow import InterviewAnswerWorkflow
from app.modules.interview.context import (
    InterviewContextProvider,
    InterviewEvaluationContextProvider,
)
from app.modules.interview.domain import InterviewStatus
from app.modules.interview.exceptions import (
    InterviewEvaluationError,
    RetryableInterviewPreparationError,
)
from app.modules.interview.follow_up import FollowUpPolicy
from app.modules.interview.repository import SqlAlchemyInterviewRepository
from app.modules.interview.workflow import (
    InterviewPreparationWorkflow,
    InterviewResumeEvaluationWorkflow,
)
from app.modules.knowledge.context import ContextAssembler
from app.modules.knowledge.domain import utc_now
from app.modules.knowledge.exceptions import RetryableKnowledgeImportError
from app.modules.knowledge.repository import (
    SqlAlchemyKnowledgeRepository,
)
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter
from app.modules.report.repository import SqlAlchemyInterviewReportRepository
from app.modules.report.service import InterviewReportService, ReportGenerationRetryableError
from app.workers.queue import (
    DocumentImportJob,
    InterviewAnswerEvaluationJob,
    InterviewPreparationJob,
    InterviewReportGenerationJob,
    InterviewResumeEvaluationJob,
    InterviewResumeEvaluationTaskQueuePort,
)
from app.workers.redis_queue import (
    DOCUMENT_IMPORT_QUEUE,
    ArqDocumentTaskQueue,
    enqueue_document_job,
    enqueue_interview_answer_evaluation_job,
    enqueue_interview_preparation_job,
    enqueue_interview_report_job,
)

logger = logging.getLogger(__name__)
WORKER_HEALTH_KEY = "knowledge-import-worker:health"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def _queue_wait_ms(ctx: dict[str, Any]) -> float | None:
    """Return ARQ queue latency when the worker context provides an enqueue time."""

    enqueue_time = ctx.get("enqueue_time")
    if not isinstance(enqueue_time, datetime):
        return None
    now = datetime.now(tz=enqueue_time.tzinfo) if enqueue_time.tzinfo else datetime.now()
    return round(max(0.0, (now - enqueue_time).total_seconds() * 1000), 2)


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
    logger.info(
        "Knowledge document dequeued",
        extra={
            "document_id": document_id,
            "knowledge_base_id": knowledge_base_id,
            "request_id": request_id,
            "attempt": job_try,
            "queue_wait_ms": _queue_wait_ms(ctx),
        },
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
            cast(InterviewResumeEvaluationTaskQueuePort, ctx["document_task_queue"]),
        )
        common_log = {
            "session_id": session_id,
            "user_id": user_id,
            "request_id": request_id,
            "attempt": job_try,
            "provider": settings.ai_provider,
            "queue_wait_ms": _queue_wait_ms(ctx),
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
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Interview preparation completed duration_ms=%s queue_wait_ms=%s "
            "context_retrieval_ms=%s question_generation_ms=%s "
            "question_generation_attempts=%s question_validation_retry_count=%s "
            "database_storage_ms=%s status=%s",
            duration_ms,
            common_log["queue_wait_ms"],
            workflow.timings.get("context_retrieval_ms"),
            workflow.timings.get("question_generation_ms"),
            workflow.timings.get("question_generation_attempts"),
            workflow.timings.get("question_validation_retry_count", 0),
            workflow.timings.get("database_storage_ms"),
            result.status.value,
            extra={
                **common_log,
                "duration_ms": duration_ms,
                "preparation_duration_ms": duration_ms,
                "context_retrieval_ms": workflow.timings.get("context_retrieval_ms"),
                "resume_evaluation_ms": None,
                "question_generation_ms": workflow.timings.get("question_generation_ms"),
                "question_generation_attempts": workflow.timings.get(
                    "question_generation_attempts"
                ),
                "question_validation_retry_count": workflow.timings.get(
                    "question_validation_retry_count", 0
                ),
                "database_storage_ms": workflow.timings.get("database_storage_ms"),
                "status": result.status.value,
            },
        )


async def process_interview_resume_evaluation(
    ctx: dict[str, Any],
    *,
    session_id: str,
    user_id: str,
    request_id: str,
) -> None:
    """Evaluate a resume after preparation using a separate DB session."""

    settings = cast(Settings, ctx["settings"])
    job_try = int(ctx.get("job_try", 1))
    job = InterviewResumeEvaluationJob(
        session_id=UUID(session_id),
        user_id=UUID(user_id),
        request_id=request_id,
    )
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    started_at = time.perf_counter()
    async with session_factory() as session:
        repository = SqlAlchemyInterviewRepository(session)
        workflow = InterviewResumeEvaluationWorkflow(
            repository,
            InterviewContextProvider(
                SqlAlchemyKnowledgeRepository(session),
                ctx["embedding"],
                PgVectorRetriever(session, settings.embedding_dimensions),
                ContextAssembler(settings.rag_max_context_tokens, settings.rag_max_chunk_tokens),
                settings,
            ),
            ctx["resume_evaluator"],
        )
        common_log = {
            "session_id": session_id,
            "user_id": user_id,
            "request_id": request_id,
            "attempt": job_try,
            "provider": settings.ai_provider,
        }
        logger.info("Interview resume evaluation started", extra=common_log)
        try:
            result = await workflow.evaluate(job.user_id, job.session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Interview resume evaluation task failed",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            return
        logger.info(
            "Interview resume evaluation completed",
            extra={
                **common_log,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "context_retrieval_ms": workflow.timings.get("context_retrieval_ms"),
                "resume_evaluation_ms": workflow.timings.get("resume_evaluation_ms"),
                "database_storage_ms": workflow.timings.get("database_storage_ms"),
                "status": result.status.value if result is not None else None,
            },
        )


async def process_interview_answer_evaluation(
    ctx: dict[str, Any],
    *,
    user_id: str,
    session_id: str,
    turn_id: str,
    answer_id: str,
    request_id: str,
) -> None:
    """Evaluate one answer after an atomic PostgreSQL claim."""

    settings = cast(Settings, ctx["settings"])
    job_try = int(ctx.get("job_try", 1))
    job = InterviewAnswerEvaluationJob(
        user_id=UUID(user_id),
        session_id=UUID(session_id),
        turn_id=UUID(turn_id),
        answer_id=UUID(answer_id),
        request_id=request_id,
    )
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    started_at = time.perf_counter()
    async with session_factory() as session:
        repository = SqlAlchemyInterviewRepository(session)
        stale_before = utc_now() - timedelta(seconds=settings.interview_answer_stale_seconds)
        claimed = await repository.claim_evaluation(
            job.session_id,
            job.turn_id,
            job.user_id,
            job.answer_id,
            job.request_id,
            stale_before,
            job_try,
        )
        if not claimed:
            return
        common_log = {
            "session_id": session_id,
            "turn_id": turn_id,
            "answer_id": answer_id,
            "request_id": request_id,
            "attempt": job_try,
            "provider": settings.ai_provider,
        }
        logger.info("Interview answer evaluation started", extra=common_log)
        if (
            settings.ai_provider == "unavailable"
            or settings.embedding_provider == "unavailable"
        ):
            await repository.fail_evaluation(
                job.session_id,
                job.turn_id,
                job.user_id,
                "INTERVIEW_EVALUATION_PROVIDER_UNAVAILABLE",
                "Interview evaluation provider is not configured",
            )
            return

        workflow = InterviewAnswerWorkflow(
            repository,
            InterviewEvaluationContextProvider(
                SqlAlchemyKnowledgeRepository(session),
                ctx["embedding"],
                PgVectorRetriever(session, settings.embedding_dimensions),
                ContextAssembler(settings.rag_max_context_tokens, settings.rag_max_chunk_tokens),
                settings,
            ),
            ctx["interview_answer_evaluator"],
            ctx["follow_up_question_generator"],
            FollowUpPolicy(
                max_depth=settings.interview_max_follow_up_depth,
                score_threshold=settings.interview_follow_up_score_threshold,
                max_follow_ups_per_session=settings.interview_max_follow_ups_per_session,
                min_answer_length=settings.interview_min_answer_length,
                max_answer_length=settings.interview_max_answer_length,
            ),
        )
        try:
            result = await workflow.evaluate(
                job.user_id,
                job.session_id,
                job.turn_id,
                "",
                answer_id=job.answer_id,
                request_id=job.request_id,
                worker_mode=True,
            )
        except asyncio.CancelledError:
            raise
        except InterviewEvaluationError as exc:
            await repository.fail_evaluation(
                job.session_id,
                job.turn_id,
                job.user_id,
                exc.code,
                _safe_evaluation_failure_message(exc),
            )
            logger.warning(
                "Interview answer evaluation failed permanently",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "failure_code": exc.code,
                },
            )
            return
        except AppError as exc:
            await repository.fail_evaluation(
                job.session_id,
                job.turn_id,
                job.user_id,
                exc.code,
                "Interview evaluation could not be completed",
            )
            logger.warning(
                "Interview answer evaluation rejected",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "failure_code": exc.code,
                },
            )
            return
        except Exception as exc:
            if job_try >= settings.interview_answer_task_max_attempts:
                await repository.fail_evaluation(
                    job.session_id,
                    job.turn_id,
                    job.user_id,
                    "INTERVIEW_EVALUATION_RETRY_EXHAUSTED",
                    "Interview evaluation failed after several attempts",
                )
                logger.warning(
                    "Interview answer evaluation exhausted retries",
                    extra={
                        **common_log,
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                        "failure_code": "INTERVIEW_EVALUATION_RETRY_EXHAUSTED",
                    },
                )
                return
            delay = settings.interview_answer_retry_base_seconds * (2 ** (job_try - 1))
            logger.warning(
                "Interview answer evaluation will retry",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "retry_delay_seconds": delay,
                    "failure_category": type(exc).__name__,
                },
            )
            raise Retry(defer=delay) from exc
        logger.info(
            "Interview answer evaluation completed",
            extra={
                **common_log,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "status": result.status.value,
            },
        )


async def process_interview_report_generation(
    ctx: dict[str, Any],
    *,
    report_id: str,
    session_id: str,
    user_id: str,
    request_id: str,
) -> None:
    """Generate one immutable report with an independent lease renewal session."""

    settings = cast(Settings, ctx["settings"])
    job_try = int(ctx.get("job_try", 1))
    job = InterviewReportGenerationJob(
        report_id=UUID(report_id),
        session_id=UUID(session_id),
        user_id=UUID(user_id),
        request_id=request_id,
    )
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    started_at = time.perf_counter()
    async with session_factory() as session, session_factory() as lease_session:
        repository = SqlAlchemyInterviewRepository(session)
        report_repository = SqlAlchemyInterviewReportRepository(session)
        lease_repository = SqlAlchemyInterviewReportRepository(lease_session)
        service = InterviewReportService(
            repository,
            report_repository,
            ctx["interview_report_narrative"],
            cast(ArqDocumentTaskQueue, ctx["document_task_queue"]),
            settings,
        )
        common_log = {
            "report_id": report_id,
            "session_id": session_id,
            "user_id": user_id,
            "request_id": request_id,
            "attempt": job_try,
            "provider": settings.ai_provider,
        }
        logger.info("Interview report generation started", extra=common_log)
        try:
            await service.process_generation_job(
                job,
                job_try,
                lease_repository=lease_repository,
            )
        except ReportGenerationRetryableError as exc:
            delay = max(exc.delay_seconds, settings.report_retry_base_seconds)
            logger.warning(
                "Interview report generation will retry",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "retry_delay_seconds": delay,
                },
            )
            raise Retry(defer=delay) from exc
        logger.info(
            "Interview report generation finished",
            extra={
                **common_log,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )


def _safe_evaluation_failure_message(exc: InterviewEvaluationError) -> str:
    if exc.code == "interview_evaluation_invalid":
        return "Interview evaluation output was invalid"
    return "Interview evaluation could not be completed"


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
    ctx["interview_answer_evaluator"] = providers.interview_answer_evaluator
    ctx["follow_up_question_generator"] = providers.follow_up_question_generator
    ctx["interview_report_narrative"] = providers.interview_report_narrative
    ctx["file_storage"] = LocalFileStorage(settings.knowledge_storage_dir)
    ctx["pdf_parser"] = PypdfPdfParser()
    ctx["text_splitter"] = SimpleTextSplitter(
        settings.rag_chunk_size,
        settings.rag_chunk_overlap,
    )
    ctx["document_task_queue"] = ArqDocumentTaskQueue.create(str(settings.redis_url))
    await _recover_stale_documents(ctx)
    await _recover_interview_preparations(ctx)
    await _recover_interview_evaluations(ctx)
    await _recover_interview_reports(ctx)
    ctx["interview_recovery_task"] = asyncio.create_task(
        _interview_recovery_loop(ctx),
        name="interview-recovery",
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


async def _recover_interview_evaluations(ctx: dict[str, Any]) -> None:
    settings = cast(Settings, ctx["settings"])
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    redis = cast(ArqRedis, ctx["redis"])
    stale_before = utc_now() - timedelta(seconds=settings.interview_answer_stale_seconds)
    async with session_factory() as session:
        repository = SqlAlchemyInterviewRepository(session)
        recoverable = await repository.list_recoverable_evaluations(
            stale_before,
            settings.interview_answer_task_max_attempts,
            settings.interview_answer_recovery_batch_size,
        )
    for session_id, user_id, turn_id, answer_id, request_id, attempt_count in recoverable:
        job = InterviewAnswerEvaluationJob(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            answer_id=answer_id,
            request_id=request_id,
            job_id=f"interview-answer-evaluation:{turn_id}:{attempt_count}",
        )
        await enqueue_interview_answer_evaluation_job(redis, job)
        logger.info(
            "Recovered interview answer evaluation job",
            extra={
                "session_id": str(session_id),
                "turn_id": str(turn_id),
                "answer_id": str(answer_id),
                "request_id": request_id,
                "attempt": attempt_count,
                "provider": settings.ai_provider,
            },
        )


async def _recover_interview_reports(ctx: dict[str, Any]) -> None:
    settings = cast(Settings, ctx["settings"])
    session_factory = cast(async_sessionmaker[AsyncSession], ctx["session_factory"])
    redis = cast(ArqRedis, ctx["redis"])
    stale_before = utc_now() - timedelta(seconds=settings.report_generation_stale_seconds)
    async with session_factory() as session:
        repository = SqlAlchemyInterviewReportRepository(session)
        recoverable = await repository.list_recoverable_generations(
            stale_before,
            settings.report_task_max_attempts,
            settings.report_recovery_batch_size,
        )
        for report in recoverable:
            await repository.mark_queued(report.id, report.user_id)
    for report in recoverable:
        attempt = report.generation_attempt_count + 1
        job = InterviewReportGenerationJob(
            report_id=report.id,
            session_id=report.session_id,
            user_id=report.user_id,
            request_id=f"recovery:{report.id}",
            job_id=f"interview-report-generation:{report.id}:{attempt}",
        )
        await enqueue_interview_report_job(redis, job)
        logger.info(
            "Recovered interview report generation job",
            extra={
                "report_id": str(report.id),
                "session_id": str(report.session_id),
                "user_id": str(report.user_id),
                "request_id": job.request_id,
                "attempt": attempt,
                "provider": settings.ai_provider,
            },
        )


async def _interview_recovery_loop(ctx: dict[str, Any]) -> None:
    settings = cast(Settings, ctx["settings"])
    while True:
        await asyncio.sleep(
            min(
                settings.interview_preparation_recovery_interval_seconds,
                settings.interview_answer_recovery_interval_seconds,
                settings.report_recovery_interval_seconds,
            )
        )
        try:
            await _recover_interview_preparations(ctx)
            await _recover_interview_evaluations(ctx)
            await _recover_interview_reports(ctx)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Interview recovery failed")


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
        functions=[
            process_knowledge_document,
            process_interview_preparation,
            process_interview_resume_evaluation,
            process_interview_answer_evaluation,
            process_interview_report_generation,
        ],
        queue_name=DOCUMENT_IMPORT_QUEUE,
        redis_settings=RedisSettings.from_dsn(str(settings.redis_url)),
        on_startup=worker_startup,
        on_shutdown=worker_shutdown,
        max_jobs=4,
        job_timeout=max(
            settings.knowledge_task_timeout_seconds,
            settings.interview_preparation_task_timeout_seconds,
            settings.interview_answer_task_timeout_seconds,
            settings.report_task_timeout_seconds,
        ),
        max_tries=max(
            settings.knowledge_task_max_attempts,
            settings.interview_preparation_task_max_attempts,
            settings.interview_answer_task_max_attempts,
            settings.report_task_max_attempts,
        ),
        retry_jobs=True,
        health_check_interval=15,
        health_check_key=WORKER_HEALTH_KEY,
        log_results=False,
    )


if __name__ == "__main__":
    create_worker().run()
