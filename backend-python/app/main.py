from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from app.ai.factory import AiProviderFactory
from app.api.v1.ai_properties import router as ai_properties_router
from app.api.v1.chat import router as chat_router
from app.api.v1.interview import router as interview_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.exceptions import (
    AppError,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.redis import create_redis_client
from app.infrastructure.storage.files import LocalFileStorage
from app.infrastructure.storage.pdf import PypdfPdfParser
from app.workers.queue import InlineTaskQueue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and close async infrastructure clients with the application lifecycle."""

    settings = get_settings()
    providers = AiProviderFactory.build(settings)
    if settings.embedding_provider != "unavailable":
        await AiProviderFactory.validate_embedding_dimensions(
            providers.embedding,
            settings.embedding_dimensions,
        )
    engine = create_database_engine(str(settings.database_url))
    app.state.database_engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = create_redis_client(str(settings.redis_url))
    app.state.chat_model = providers.chat_model
    app.state.interview_question_generator = providers.interview_question_generator
    app.state.interview_answer_evaluator = providers.interview_answer_evaluator
    app.state.follow_up_question_generator = providers.follow_up_question_generator
    app.state.interview_report_narrative = providers.interview_report_narrative
    app.state.resume_evaluator = providers.resume_evaluator
    app.state.embedding = providers.embedding
    app.state.ai_model_metadata = providers.model_metadata
    app.state.file_storage = LocalFileStorage(settings.knowledge_storage_dir)
    app.state.pdf_parser = PypdfPdfParser()
    app.state.task_queue = InlineTaskQueue()
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    """Create the HTTP application without establishing external connections."""

    app = FastAPI(title="AI Interview API", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(AppError, cast(ExceptionHandler, app_exception_handler))
    app.add_exception_handler(
        StarletteHTTPException, cast(ExceptionHandler, http_exception_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api")
    app.include_router(ai_properties_router, prefix="/api")
    app.include_router(knowledge_router, prefix="/api")
    app.include_router(interview_router, prefix="/api")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Keep the original health endpoint as a liveness-compatible alias."""

        return {"status": "ok"}

    @app.get("/health/live", tags=["system"])
    async def health_live() -> dict[str, str]:
        """Return process liveness without contacting external dependencies."""

        return {"status": "ok"}

    @app.get("/health/ready", response_model=None, tags=["system"])
    async def health_ready() -> JSONResponse | dict[str, str]:
        """Verify database and Redis connectivity without exposing configuration."""

        database_engine = getattr(app.state, "database_engine", None)
        redis = getattr(app.state, "redis", None)
        if database_engine is None or redis is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        try:
            async with database_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            if not await redis.ping():
                raise RuntimeError("Redis did not respond")
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ok"}

    return app


app = create_app()
