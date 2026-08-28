from typing import cast

from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    """Create an asyncio Redis client; the connection is established lazily."""

    return cast(Redis, Redis.from_url(redis_url, encoding="utf-8", decode_responses=True))
