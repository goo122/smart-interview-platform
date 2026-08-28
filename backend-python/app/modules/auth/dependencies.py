from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
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


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
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
