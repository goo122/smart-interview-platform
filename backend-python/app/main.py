from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from app.ai.chat import UnavailableChatModel
from app.ai.embedding import UnavailableEmbedding
from app.api.v1.chat import router as chat_router
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
    engine = create_database_engine(str(settings.database_url))
    app.state.database_engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = create_redis_client(str(settings.redis_url))
    app.state.chat_model = UnavailableChatModel()
    app.state.embedding = UnavailableEmbedding(settings.embedding_dimensions)
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
    app.include_router(knowledge_router, prefix="/api")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Return process liveness; dependency readiness checks will be added separately."""

        return {"status": "ok"}

    return app


app = create_app()
