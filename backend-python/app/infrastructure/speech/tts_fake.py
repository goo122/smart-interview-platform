"""Deterministic, browser-playable TTS adapter for tests and local development."""

from __future__ import annotations

import io
import wave

from app.modules.speech.tts_ports import TextToSpeechRequest, TextToSpeechResult


class FakeTextToSpeechAdapter:
    provider_name = "fake"
    is_available = True
    supported_audio_formats = ("wav", "mp3", "lame")
    supported_voices = ("x4_mingge",)
    max_text_length = 10000
    supports_streaming = False

    def __init__(self) -> None:
        self.calls = 0

    async def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        self.calls += 1
        # A short silent WAV is deliberately independent of the input text and
        # valid in every browser, while the service still validates the text.
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(request.sample_rate)
            output.writeframes(b"\x00\x00" * max(1, min(len(request.text) * 80, 1600)))
        return TextToSpeechResult(
            audio_bytes=buffer.getvalue(),
            audio_format="wav",
            content_type="audio/wav",
        )
