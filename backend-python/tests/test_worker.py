import pytest

from app.workers.worker import worker_shutdown


class RecordingQueue:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class RecordingEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


@pytest.mark.asyncio
async def test_worker_shutdown_releases_queue_and_database_resources() -> None:
    queue = RecordingQueue()
    engine = RecordingEngine()
    context = {"document_task_queue": queue, "engine": engine}

    await worker_shutdown(context)  # type: ignore[arg-type]

    assert queue.closed
    assert engine.disposed
    assert context == {}
