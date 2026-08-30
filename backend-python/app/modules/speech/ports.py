"""Provider-neutral ports for streaming speech recognition."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

SpeechRecognitionStatus = Literal["partial", "final"]


@dataclass(frozen=True, slots=True)
class SpeechAudioFormat:
    """The audio format accepted by a speech recognition session."""

    encoding: str
    sample_rate: int
    channels: int


@dataclass(frozen=True, slots=True)
class SpeechRecognitionEvent:
    """A provider result represented as a complete, displayable text snapshot."""

    text: str
    status: SpeechRecognitionStatus
    revision: int
    segment_id: int | None = None


class SpeechToTextSession(Protocol):
    """Async lifecycle for one provider-side streaming session."""

    async def send_audio(self, audio: bytes) -> None:
        """Send one bounded PCM frame with provider backpressure."""

    async def finish(self) -> None:
        """Signal that no more audio frames will be sent."""

    def events(self) -> AsyncIterator[SpeechRecognitionEvent | None]:
        """Yield provider events and ``None`` exactly once after provider completion."""

    async def close(self) -> None:
        """Release provider sockets, tasks and buffers."""


class SpeechToTextPort(Protocol):
    """Vendor-independent speech recognition adapter."""

    @property
    def provider_name(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        ...

    @property
    def supported_audio_formats(self) -> Sequence[str]:
        ...

    async def create_session(self, audio_format: SpeechAudioFormat) -> SpeechToTextSession:
        ...
