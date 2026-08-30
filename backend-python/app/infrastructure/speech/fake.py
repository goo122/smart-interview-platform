"""Deterministic speech-to-text adapter for local development and tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from app.modules.speech.ports import (
    SpeechAudioFormat,
    SpeechRecognitionEvent,
)


class FakeSpeechToTextAdapter:
    """Emit deterministic snapshots without decoding or contacting a provider."""

    provider_name = "fake"
    is_available = True

    def __init__(
        self,
        *,
        partial_texts: Sequence[str] = ("这是 Fake Provider 的语音转写结果。",),
        final_text: str | None = None,
    ) -> None:
        self._partial_texts = tuple(text.strip() for text in partial_texts if text.strip())
        self._final_text = final_text.strip() if final_text else None
        self.sessions: list[FakeSpeechToTextSession] = []

    @property
    def supported_audio_formats(self) -> Sequence[str]:
        return ("pcm_s16le",)

    async def create_session(self, audio_format: SpeechAudioFormat) -> FakeSpeechToTextSession:
        session = FakeSpeechToTextSession(
            partial_texts=self._partial_texts,
            final_text=self._final_text,
        )
        self.sessions.append(session)
        return session


class FakeSpeechToTextSession:
    """A bounded event queue makes the fake follow the same async contract as a provider."""

    def __init__(self, *, partial_texts: Sequence[str], final_text: str | None) -> None:
        self._partial_texts = tuple(partial_texts)
        self._final_text = final_text
        self._events: asyncio.Queue[SpeechRecognitionEvent | None] = asyncio.Queue(maxsize=8)
        self._chunk_count = 0
        self._revision = 0
        self._last_text = ""
        self._finished = False
        self.closed = False

    async def send_audio(self, audio: bytes) -> None:
        if self.closed or self._finished:
            return
        if not audio:
            return

        self._chunk_count += 1
        if self._partial_texts:
            text = self._partial_texts[
                min(self._chunk_count - 1, len(self._partial_texts) - 1)
            ]
        else:
            text = f"Fake Provider 音频片段 {self._chunk_count}"
        if text == self._last_text:
            return
        self._last_text = text
        self._revision += 1
        await self._events.put(
            SpeechRecognitionEvent(text=text, status="partial", revision=self._revision)
        )

    async def finish(self) -> None:
        if self.closed or self._finished:
            return
        self._finished = True
        final_text = self._final_text or self._last_text
        if final_text:
            self._revision += 1
            await self._events.put(
                SpeechRecognitionEvent(
                    text=final_text,
                    status="final",
                    revision=self._revision,
                )
            )
        await self._events.put(None)

    async def _receive_event(self) -> SpeechRecognitionEvent | None:
        return await self._events.get()

    def events(self) -> AsyncIterator[SpeechRecognitionEvent | None]:
        async def iterator() -> AsyncIterator[SpeechRecognitionEvent | None]:
            while True:
                event = await self._receive_event()
                yield event
                if event is None:
                    return

        return iterator()

    async def close(self) -> None:
        self.closed = True
        self._finished = True
        while not self._events.empty():
            self._events.get_nowait()
