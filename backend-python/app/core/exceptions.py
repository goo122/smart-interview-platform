from typing import Any, ClassVar

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base exception for expected application errors."""

    status_code: ClassVar[int] = 400
    code: ClassVar[str] = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_failed"


class UserAlreadyExistsError(AppError):
    status_code = 409
    code = "user_already_exists"


class InvalidRefreshTokenError(AuthenticationError):
    """Raised when a refresh token is invalid, expired, or revoked."""

    code = "invalid_refresh_token"


class ConversationNotFoundError(AppError):
    status_code = 404
    code = "conversation_not_found"


class ConversationFinishedError(AppError):
    status_code = 409
    code = "conversation_finished"


class InvalidChatRequestError(AppError):
    status_code = 400
    code = "invalid_chat_request"


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    """Build the single error envelope returned by this API."""

    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Convert framework HTTP errors, including 404, to the standard envelope."""

    code = "not_found" if exc.status_code == 404 else "http_error"
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return error_response(status_code=exc.status_code, code=code, message=message)


async def app_exception_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Convert expected domain errors to the standard API error envelope."""

    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation failures without exposing framework-specific response shapes."""

    details = [
        {
            "loc": error.get("loc", ()),
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=details,
    )


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Avoid leaking internal error information to API clients."""

    return error_response(
        status_code=500,
        code="internal_server_error",
        message="An unexpected error occurred",
    )
