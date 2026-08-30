"""Provider-neutral ports for text-to-speech."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TextToSpeechRequest:
    """Validated synthesis options passed to an infrastructure adapter."""

    text: str
    voice: str
    language: str
    speed: int
    volume: int
    pitch: int
    rhythm: int
    audio_format: str
    sample_rate: int
    timeout_seconds: float
    poll_interval_seconds: float


@dataclass(frozen=True, slots=True)
class TextToSpeechResult:
    """Audio returned by a provider without exposing provider-specific metadata."""

    audio_bytes: bytes
    audio_format: str
    content_type: str


class TextToSpeechPort(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def is_available(self) -> bool:
        ...

    @property
    def supported_audio_formats(self) -> Sequence[str]:
        ...

    @property
    def supported_voices(self) -> Sequence[str]:
        ...

    @property
    def max_text_length(self) -> int:
        ...

    @property
    def supports_streaming(self) -> bool:
        ...

    async def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        """Synthesize one bounded text request."""
