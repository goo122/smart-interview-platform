from collections.abc import AsyncIterator
from typing import Annotated, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Request, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import TokenService
from app.modules.auth.domain import User
from app.modules.auth.repository import SqlAlchemyUserRepository, UserRepository
from app.modules.auth.service import AuthService
from app.modules.auth.session_store import RedisSessionStore, SessionStore

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.session_factory,
    )
    async with session_factory() as session:
        yield session


async def get_websocket_db_session(websocket: WebSocket) -> AsyncIterator[AsyncSession]:
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        websocket.app.state.session_factory,
    )
    async with session_factory() as session:
        yield session


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


async def get_websocket_user_repository(
    session: Annotated[AsyncSession, Depends(get_websocket_db_session)],
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


async def get_session_store(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionStore:
    redis = cast(Redis, request.app.state.redis)
    ttl_seconds = settings.refresh_token_expire_days * 24 * 60 * 60
    return RedisSessionStore(redis, revocation_ttl_seconds=ttl_seconds)


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenService:
    return TokenService(settings)


def get_auth_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    session_store: Annotated[SessionStore, Depends(get_session_store)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(user_repository, session_store, token_service, settings=settings)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    if credentials is None:
        raise AuthenticationError("Authentication failed")
    return await service.current_user(credentials.credentials)


def _websocket_token(websocket: WebSocket) -> str | None:
    for name in ("token", "access_token", "Authorization", "authorization"):
        value = websocket.query_params.get(name)
        if not value:
            continue
        normalized = value.strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        if normalized:
            return normalized
    return None


def _reject_websocket_auth() -> NoReturn:
    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="Authentication failed",
    )


async def get_current_websocket_user(
    websocket: WebSocket,
    user_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    repository: Annotated[UserRepository, Depends(get_websocket_user_repository)],
) -> User:
    """Authenticate a browser websocket without trusting the path user ID."""

    token = _websocket_token(websocket)
    if token is None:
        _reject_websocket_auth()

    try:
        claims = TokenService(settings).decode_access(token)
    except AuthenticationError:
        _reject_websocket_auth()

    current_user = await repository.get_by_id(claims.sub)
    if current_user is None or not current_user.is_active:
        _reject_websocket_auth()

    target_user = None
    try:
        target_user = await repository.get_by_id(UUID(user_id))
    except ValueError:
        target_user = await repository.get_by_username(user_id)
    if target_user is None or target_user.id != current_user.id:
        _reject_websocket_auth()
    return current_user
