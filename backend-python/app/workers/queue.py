from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class TaskQueuePort(Protocol):
    """Legacy in-process queue port used by workflows not yet migrated to ARQ."""

    async def enqueue(self, task: Callable[[], Awaitable[None]]) -> None: ...


class InlineTaskQueue:
    """Synchronous queue retained for tests and workflows outside this migration."""

    async def enqueue(self, task: Callable[[], Awaitable[None]]) -> None:
        await task()


class RetryableTaskError(RuntimeError):
    """Internal signal for an in-process queue to retry a task."""


@dataclass(frozen=True, slots=True)
class DocumentImportJob:
    """Serializable arguments for a knowledge-document import task."""

    document_id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    request_id: str


DocumentImportHandler = Callable[[DocumentImportJob, int], Awaitable[None]]


class DocumentTaskQueuePort(Protocol):
    """Queue port whose payload is safe to serialize into Redis."""

    async def enqueue_document(self, job: DocumentImportJob) -> None: ...

    def bind_inline_handler(self, handler: DocumentImportHandler) -> None: ...


@dataclass(frozen=True, slots=True)
class InterviewPreparationJob:
    """Serializable arguments for an interview-preparation task."""

    session_id: UUID
    user_id: UUID
    request_id: str
    job_id: str | None = None


class InterviewPreparationTaskQueuePort(Protocol):
    """Queue port for asynchronously preparing interview questions."""

    async def enqueue_interview_preparation(
        self, job: InterviewPreparationJob
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class InterviewAnswerEvaluationJob:
    """Serializable arguments for an interview-answer evaluation task."""

    user_id: UUID
    session_id: UUID
    turn_id: UUID
    answer_id: UUID
    request_id: str
    job_id: str | None = None


class InterviewAnswerEvaluationTaskQueuePort(Protocol):
    """Queue port for asynchronously evaluating one submitted answer."""

    async def enqueue_interview_answer_evaluation(
        self, job: InterviewAnswerEvaluationJob
    ) -> None: ...


class InlineDocumentTaskQueue:
    """In-process document queue substitute used by unit/API tests only."""

    def __init__(self, max_attempts: int = 3) -> None:
        self._handler: DocumentImportHandler | None = None
        self._max_attempts = max_attempts

    def bind_inline_handler(self, handler: DocumentImportHandler) -> None:
        self._handler = handler

    async def enqueue_document(self, job: DocumentImportJob) -> None:
        if self._handler is None:
            raise RuntimeError("Inline document queue has no handler")
        for attempt in range(1, self._max_attempts + 1):
            try:
                await self._handler(job, attempt)
            except RetryableTaskError:
                if attempt >= self._max_attempts:
                    raise
