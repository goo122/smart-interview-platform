from typing import Protocol, cast
from uuid import UUID

from redis.asyncio import Redis


class SessionStore(Protocol):
    """Port for refresh-token sessions and revocation state."""

    async def save_refresh_session(self, jti: UUID, user_id: UUID, ttl_seconds: int) -> None: ...

    async def consume_refresh_session(self, jti: UUID) -> UUID | None: ...

    async def revoke_refresh_session(self, jti: UUID, ttl_seconds: int) -> None: ...


class RedisSessionStore:
    """Redis implementation using one active key and a short-lived revocation marker."""

    def __init__(self, redis: Redis, revocation_ttl_seconds: int | None = None) -> None:
        self._redis = redis
        self._revocation_ttl_seconds = revocation_ttl_seconds

    async def save_refresh_session(self, jti: UUID, user_id: UUID, ttl_seconds: int) -> None:
        await self._redis.set(_active_key(jti), str(user_id), ex=ttl_seconds)

    async def consume_refresh_session(self, jti: UUID) -> UUID | None:
        value = cast(str | None, await self._redis.getdel(_active_key(jti)))
        if value is None:
            return None
        try:
            user_id = UUID(value)
            if self._revocation_ttl_seconds is not None:
                await self._redis.set(
                    _revoked_key(jti), "1", ex=self._revocation_ttl_seconds
                )
            return user_id
        except ValueError:
            return None

    async def revoke_refresh_session(self, jti: UUID, ttl_seconds: int) -> None:
        await self._redis.delete(_active_key(jti))
        await self._redis.set(_revoked_key(jti), "1", ex=ttl_seconds)


def _active_key(jti: UUID) -> str:
    return f"auth:refresh:{jti}"


def _revoked_key(jti: UUID) -> str:
    return f"auth:refresh:revoked:{jti}"
