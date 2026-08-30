"""Application service for bounded, authenticated text-to-speech requests."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.core.config import Settings
from app.modules.speech.tts_exceptions import (
    InvalidTextToSpeechRequestError,
    TextToSpeechFailedError,
    TextToSpeechIdempotencyConflictError,
    TextToSpeechProviderError,
    TextToSpeechProviderUnavailable,
    TextToSpeechRateLimitError,
    TextToSpeechTaskNotFoundError,
    TextToSpeechUnavailableError,
)
from app.modules.speech.tts_ports import TextToSpeechPort, TextToSpeechRequest, TextToSpeechResult


@dataclass(frozen=True, slots=True)
class TtsCapabilities:
    available: bool
    provider: str
    supported_audio_formats: tuple[str, ...]
    supported_voices: tuple[str, ...]
    max_text_length: int
    supports_streaming: bool


@dataclass(frozen=True, slots=True)
class TtsSynthesisRecord:
    task_id: UUID
    user_id: UUID
    audio_base64: str
    audio_format: str
    content_type: str
    expires_at: datetime


class TtsRequestPayload(Protocol):
    def model_dump(self, *, by_alias: bool) -> dict[str, Any]: ...


class TextToSpeechService:
    """Own validation, rate limiting, idempotency and ephemeral task records."""

    def __init__(self, provider: TextToSpeechPort, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings
        self._tasks: dict[UUID, TtsSynthesisRecord] = {}
        self._idempotency: dict[tuple[UUID, str], tuple[str, UUID]] = {}
        self._request_times: dict[UUID, deque[float]] = {}
        self._lock = asyncio.Lock()

    def capabilities(self) -> TtsCapabilities:
        provider_name = (
            self._provider.provider_name if self._provider.is_available else "unavailable"
        )
        return TtsCapabilities(
            available=self._provider.is_available,
            provider=provider_name,
            supported_audio_formats=tuple(self._provider.supported_audio_formats),
            supported_voices=tuple(self._provider.supported_voices),
            max_text_length=self._settings.tts_max_text_length,
            supports_streaming=self._provider.supports_streaming,
        )

    async def synthesize(self, user_id: UUID, payload: TtsRequestPayload) -> TtsSynthesisRecord:
        request = self._build_request(payload)
        return await self._synthesize_with_idempotency(user_id, request, self._request_id(payload))

    async def create_task(self, user_id: UUID, payload: TtsRequestPayload) -> TtsSynthesisRecord:
        return await self.synthesize(user_id, payload)

    async def get_task(self, user_id: UUID, task_id: UUID) -> TtsSynthesisRecord:
        async with self._lock:
            self._purge_expired()
            record = self._tasks.get(task_id)
            if record is None or record.user_id != user_id:
                raise TextToSpeechTaskNotFoundError("TTS task was not found")
            return record

    def _build_request(self, payload: TtsRequestPayload) -> TextToSpeechRequest:
        # The router passes the validated Pydantic DTO. Keeping this conversion
        # here prevents HTTP field names from leaking into infrastructure code.
        values = payload.model_dump(by_alias=False)
        raw_text = values.get("text")
        if not isinstance(raw_text, str):
            raise InvalidTextToSpeechRequestError("请输入需要转换的文本。")
        text = raw_text.strip()
        if not text:
            raise InvalidTextToSpeechRequestError("请输入需要转换的文本。")
        if len(text) > self._settings.tts_max_text_length:
            raise InvalidTextToSpeechRequestError(
                f"文本长度不能超过 {self._settings.tts_max_text_length} 个字符。"
            )
        if not self._provider.is_available:
            raise TextToSpeechUnavailableError("语音合成服务暂时不可用，请稍后重试。")

        audio_format_value = values.get("audio_encoding")
        audio_format = (
            audio_format_value.strip().lower()
            if isinstance(audio_format_value, str) and audio_format_value.strip()
            else self._settings.tts_audio_format
        )
        voice_value = values.get("vcn")
        voice = (
            voice_value.strip()
            if isinstance(voice_value, str) and voice_value.strip()
            else self._settings.tts_voice
        )
        language_value = values.get("language")
        language = (
            language_value.strip()
            if isinstance(language_value, str) and language_value.strip()
            else "zh"
        )
        if audio_format not in self._provider.supported_audio_formats:
            raise InvalidTextToSpeechRequestError("不支持请求的音频格式。")
        if voice not in self._provider.supported_voices:
            raise InvalidTextToSpeechRequestError("不支持请求的发音人。")
        sample_rate = _int_value(values.get("sample_rate"), self._settings.tts_sample_rate)
        if sample_rate != self._settings.tts_sample_rate:
            raise InvalidTextToSpeechRequestError("不支持请求的采样率。")

        return TextToSpeechRequest(
            text=text,
            voice=voice,
            language=language,
            speed=_int_value(values.get("speed"), 50),
            volume=_int_value(values.get("volume"), 50),
            pitch=_int_value(values.get("pitch"), 50),
            rhythm=_int_value(values.get("rhy"), 0),
            audio_format=audio_format,
            sample_rate=sample_rate,
            timeout_seconds=min(
                _float_value(
                    values.get("timeout_seconds"),
                    self._settings.tts_request_timeout_seconds,
                ),
                self._settings.tts_request_timeout_seconds,
            ),
            poll_interval_seconds=max(
                0.1, _int_value(values.get("poll_interval_ms"), 1500) / 1000
            ),
        )

    async def _synthesize_with_idempotency(
        self, user_id: UUID, request: TextToSpeechRequest, request_id: str | None
    ) -> TtsSynthesisRecord:
        fingerprint = _request_fingerprint(request)
        async with self._lock:
            self._purge_expired()
            if request_id:
                key = (user_id, request_id)
                existing = self._idempotency.get(key)
                if existing:
                    if existing[0] != fingerprint:
                        raise TextToSpeechIdempotencyConflictError(
                            "requestId 已用于其他 TTS 请求。"
                        )
                    cached = self._tasks.get(existing[1])
                    if cached is not None:
                        return cached

            self._check_rate_limit(user_id)

            if not self._provider.is_available:
                raise TextToSpeechUnavailableError("语音合成服务暂时不可用，请稍后重试。")

            try:
                result = await asyncio.wait_for(
                    self._provider.synthesize(request),
                    timeout=request.timeout_seconds,
                )
            except asyncio.CancelledError:
                raise
            except TextToSpeechProviderUnavailable as exc:
                raise TextToSpeechUnavailableError(
                    "语音合成服务暂时不可用，请稍后重试。"
                ) from exc
            except TimeoutError as exc:
                raise TextToSpeechUnavailableError(
                    "语音合成服务响应超时，请稍后重试。"
                ) from exc
            except TextToSpeechProviderError as exc:
                raise TextToSpeechFailedError(
                    "语音合成失败，请稍后重试。"
                ) from exc
            except Exception as exc:
                raise TextToSpeechFailedError("语音合成失败，请稍后重试。") from exc

            self._validate_result(result)
            record = TtsSynthesisRecord(
                task_id=uuid4(),
                user_id=user_id,
                audio_base64=base64.b64encode(result.audio_bytes).decode("ascii"),
                audio_format=result.audio_format,
                content_type=result.content_type,
                expires_at=datetime.now(UTC)
                + timedelta(seconds=self._settings.tts_task_ttl_seconds),
            )
            self._tasks[record.task_id] = record
            if request_id:
                self._idempotency[(user_id, request_id)] = (fingerprint, record.task_id)
            return record

    def _validate_result(self, result: TextToSpeechResult) -> None:
        if not result.audio_bytes or len(result.audio_bytes) > self._settings.tts_max_audio_bytes:
            raise TextToSpeechFailedError("语音合成返回了无效音频。")
        if result.audio_format not in {"wav", "mp3", "lame"}:
            raise TextToSpeechFailedError("语音合成返回了不支持的音频格式。")
        if not result.content_type.startswith("audio/"):
            raise TextToSpeechFailedError("语音合成返回了无效音频类型。")

    def _check_rate_limit(self, user_id: UUID) -> None:
        now = time.monotonic()
        recent = self._request_times.setdefault(user_id, deque())
        while recent and now - recent[0] >= 60:
            recent.popleft()
        if len(recent) >= self._settings.tts_max_requests_per_minute:
            raise TextToSpeechRateLimitError("语音合成请求过于频繁，请稍后再试。")
        recent.append(now)

    def _purge_expired(self) -> None:
        now = datetime.now(UTC)
        expired_ids = {task_id for task_id, task in self._tasks.items() if task.expires_at <= now}
        for task_id in expired_ids:
            self._tasks.pop(task_id, None)
        for key, (_, task_id) in list(self._idempotency.items()):
            if task_id in expired_ids:
                self._idempotency.pop(key, None)

    @staticmethod
    def _request_id(payload: TtsRequestPayload) -> str | None:
        value = payload.model_dump(by_alias=False).get("request_id")
        return value.strip() if isinstance(value, str) and value.strip() else None


def _request_fingerprint(request: TextToSpeechRequest) -> str:
    fields = "\x1f".join(
        str(value)
        for value in (
            request.text,
            request.voice,
            request.language,
            request.speed,
            request.volume,
            request.pitch,
            request.rhythm,
            request.audio_format,
            request.sample_rate,
        )
    )
    return hashlib.sha256(fields.encode("utf-8")).hexdigest()


def _int_value(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _float_value(value: Any, default: float) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default
