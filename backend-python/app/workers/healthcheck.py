import asyncio
import sys

from app.core.config import get_settings
from app.core.redis import create_redis_client
from app.workers.worker import WORKER_HEALTH_KEY


async def check() -> int:
    redis = create_redis_client(str(get_settings().redis_url))
    try:
        return 0 if await redis.exists(WORKER_HEALTH_KEY) else 1
    finally:
        await redis.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
