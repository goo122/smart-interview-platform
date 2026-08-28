from collections.abc import Awaitable, Callable
from typing import Protocol


class TaskQueuePort(Protocol):
    async def enqueue(self, task: Callable[[], Awaitable[None]]) -> None: ...


class InlineTaskQueue:
    """Synchronous queue for MVP and tests; replace with ARQ without changing the service."""

    async def enqueue(self, task: Callable[[], Awaitable[None]]) -> None:
        await task()
