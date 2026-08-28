import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ChatChunk:
    content: str


class ChatModelPort(Protocol):
    """Async streaming port used by ChatService."""

    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatChunk]: ...


class FakeChatModel:
    """Deterministic model double with configurable chunks, delay and failure."""

    def __init__(
        self,
        chunks: Sequence[str] = (),
        error: Exception | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.chunks = tuple(chunks)
        self.error = error
        self.delay_seconds = delay_seconds
        self.calls = 0
        self.cancelled = False
        self.received_messages: list[Sequence[ChatMessage]] = []

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatChunk]:
        self.calls += 1
        self.received_messages.append(tuple(messages))
        try:
            for chunk in self.chunks:
                if self.delay_seconds:
                    await asyncio.sleep(self.delay_seconds)
                yield ChatChunk(content=chunk)
            if self.error is not None:
                raise self.error
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class UnavailableChatModel:
    """Safe default when no real LLM is configured; startup remains possible."""

    async def stream(self, _messages: Sequence[ChatMessage]) -> AsyncIterator[ChatChunk]:
        for _message in _messages[:0]:
            yield ChatChunk(content="")
        raise RuntimeError("No chat model is configured")


class LangChainChatModelAdapter:
    """Small adapter around a LangChain-compatible object exposing ``astream``."""

    def __init__(self, model: Any) -> None:
        self._model = model

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[ChatChunk]:
        model_messages = [(message.role, message.content) for message in messages]
        async for chunk in self._model.astream(model_messages):
            content = getattr(chunk, "content", chunk)
            if isinstance(content, str) and content:
                yield ChatChunk(content=content)
