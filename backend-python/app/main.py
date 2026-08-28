from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from app.core.config import get_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.redis import create_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and close async infrastructure clients with the application lifecycle."""

    settings = get_settings()
    engine = create_database_engine(str(settings.database_url))
    app.state.database_engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = create_redis_client(str(settings.redis_url))
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    """Create the HTTP application without establishing external connections."""

    app = FastAPI(title="AI Interview API", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(
        StarletteHTTPException, cast(ExceptionHandler, http_exception_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Return process liveness; dependency readiness checks will be added separately."""

        return {"status": "ok"}

    return app


app = create_app()
