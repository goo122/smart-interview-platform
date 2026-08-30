"""Application orchestration for authenticated streaming speech recognition."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.modules.speech.exceptions import (
    SpeechProviderProtocolError,
    SpeechProviderUnavailableError,
)
from app.modules.speech.ports import (
    SpeechAudioFormat,
    SpeechRecognitionEvent,
    SpeechToTextPort,
    SpeechToTextSession,
)


@dataclass(frozen=True, slots=True)
class SpeechCapabilities:
    available: bool
    provider: str
    audio_format: str
    sample_rate: int
    channels: int
    supported_audio_formats: tuple[str, ...]
    supported_sample_rates: tuple[int, ...]
    max_session_seconds: int
    max_frame_bytes: int
    max_audio_bytes: int


class SpeechToTextService:
    """Own the ephemeral client/provider session and its protocol state."""

    def __init__(self, provider: SpeechToTextPort, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    def capabilities(self) -> SpeechCapabilities:
        provider_name = (
            self._provider.provider_name if self._provider.is_available else "unavailable"
        )
        return SpeechCapabilities(
            available=self._provider.is_available,
            provider=provider_name,
            audio_format=self._settings.asr_audio_format,
            sample_rate=self._settings.asr_sample_rate,
            channels=self._settings.asr_channels,
            supported_audio_formats=tuple(self._provider.supported_audio_formats),
            supported_sample_rates=(self._settings.asr_sample_rate,),
            max_session_seconds=self._settings.asr_max_session_seconds,
            max_frame_bytes=self._settings.asr_max_frame_bytes,
            max_audio_bytes=self._settings.asr_max_audio_bytes,
        )

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """Run one bounded websocket session until disconnect or normal finish."""

        await websocket.accept()
        await self._send(
            websocket,
            {
                "type": "connected",
                "message": "Speech transcription connection ready",
                "provider": self.capabilities().provider,
                "audioFormat": self._settings.asr_audio_format,
                "sampleRate": self._settings.asr_sample_rate,
                "channels": self._settings.asr_channels,
                "maxSessionSeconds": self._settings.asr_max_session_seconds,
            },
        )

        provider_session: SpeechToTextSession | None = None
        provider_iterator = None
        provider_event_task: asyncio.Task[SpeechRecognitionEvent | None] | None = None
        receive_task = asyncio.create_task(websocket.receive())
        started = False
        finishing = False
        audio_bytes = 0
        deadline = asyncio.get_running_loop().time() + self._settings.asr_max_session_seconds

        try:
            while True:
                tasks: set[asyncio.Task[Any]] = {receive_task}
                if provider_event_task is not None:
                    tasks.add(provider_event_task)
                timeout = max(0.0, deadline - asyncio.get_running_loop().time())
                done, _ = await asyncio.wait(
                    tasks,
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    await self._send_error(
                        websocket,
                        code="speech_session_timeout",
                        message="语音转写会话已超时，请重新开始录音。",
                        recoverable=False,
                    )
                    await self._close(websocket, 1008, "Speech session timeout")
                    return

                if provider_event_task is not None and provider_event_task in done:
                    completed_provider_task = provider_event_task
                    provider_event_task = None
                    try:
                        event = completed_provider_task.result()
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        await self._send_error(
                            websocket,
                            code="speech_provider_failed",
                            message="语音转写服务暂时不可用，请稍后重试。",
                            recoverable=False,
                        )
                        await self._close(websocket, 1011, "Speech provider failure")
                        return

                    if event is None:
                        if finishing:
                            await self._send(
                                websocket,
                                {
                                    "type": "closed",
                                    "message": "Speech transcription ended",
                                    "reason": "completed",
                                },
                            )
                            await self._close(websocket, 1000, "Completed")
                            return
                        await self._send_error(
                            websocket,
                            code="speech_provider_interrupted",
                            message="语音转写连接已中断，请重新开始录音。",
                            recoverable=True,
                        )
                        await self._close(websocket, 1011, "Speech provider interrupted")
                        return

                    sent = await self._send_provider_event(websocket, event)
                    if not sent:
                        return
                    provider_event_task = asyncio.create_task(
                        _next_provider_event(provider_iterator)
                    )

                if receive_task in done:
                    message = receive_task.result()
                    receive_task = asyncio.create_task(websocket.receive())
                    previous_iterator = provider_iterator
                    previous_event_task = provider_event_task
                    should_stop = await self._handle_client_message(
                        websocket,
                        message,
                        provider_session=provider_session,
                        started=started,
                        finishing=finishing,
                        audio_bytes=audio_bytes,
                    )
                    provider_session = should_stop.provider_session
                    provider_iterator = should_stop.provider_iterator or previous_iterator
                    provider_event_task = (
                        should_stop.provider_event_task or previous_event_task
                    )
                    started = should_stop.started
                    finishing = should_stop.finishing
                    audio_bytes = should_stop.audio_bytes
                    if should_stop.stop:
                        if should_stop.fatal:
                            await self._close(
                                websocket,
                                should_stop.close_code,
                                should_stop.close_reason,
                            )
                            return
                        if (
                            finishing
                            and provider_event_task is None
                            and provider_session is not None
                        ):
                            provider_event_task = asyncio.create_task(
                                _next_provider_event(provider_iterator)
                            )
                        if finishing:
                            continue
                        return
                    if (
                        provider_session is not None
                        and provider_iterator is not None
                        and provider_event_task is None
                    ):
                        provider_event_task = asyncio.create_task(
                            _next_provider_event(provider_iterator)
                        )
        finally:
            receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await receive_task
            if provider_event_task is not None:
                provider_event_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await provider_event_task
            if provider_session is not None:
                await provider_session.close()

    async def _handle_client_message(
        self,
        websocket: WebSocket,
        message: Mapping[str, Any],
        *,
        provider_session: SpeechToTextSession | None,
        started: bool,
        finishing: bool,
        audio_bytes: int,
    ) -> _ClientMessageResult:
        message_type = message.get("type")
        if message_type == "websocket.disconnect":
            return _ClientMessageResult.stop_result(
                provider_session,
                None,
                None,
                started,
                finishing,
                audio_bytes,
            )

        raw_bytes = message.get("bytes")
        if isinstance(raw_bytes, bytes):
            if not started or provider_session is None:
                await self._send_error(
                    websocket,
                    code="transcription_not_started",
                    message="请先发送开始转写指令。",
                    recoverable=True,
                )
                return _ClientMessageResult.continue_result(
                    provider_session, None, None, started, finishing, audio_bytes
                )
            if finishing:
                return _ClientMessageResult.continue_result(
                    provider_session, None, None, started, finishing, audio_bytes
                )
            frame_size = len(raw_bytes)
            if frame_size == 0 or frame_size % 2 != 0:
                await self._send_error(
                    websocket,
                    code="unsupported_audio_format",
                    message="仅支持 PCM 16-bit 音频帧。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1003,
                    close_reason="Unsupported audio format",
                )
            if frame_size > self._settings.asr_max_frame_bytes:
                await self._send_error(
                    websocket,
                    code="audio_frame_too_large",
                    message="单个音频帧超过允许大小。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1009,
                    close_reason="Audio frame too large",
                )
            next_total = audio_bytes + frame_size
            if next_total > self._settings.asr_max_audio_bytes:
                await self._send_error(
                    websocket,
                    code="audio_limit_exceeded",
                    message="本次录音超过允许的累计大小。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1009,
                    close_reason="Audio limit exceeded",
                )
            try:
                await provider_session.send_audio(raw_bytes)
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._send_error(
                    websocket,
                    code="speech_provider_failed",
                    message="语音转写服务暂时不可用，请稍后重试。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1011,
                    close_reason="Speech provider failure",
                )
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, finishing, next_total
            )

        raw_text = message.get("text")
        if not isinstance(raw_text, str):
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, finishing, audio_bytes
            )
        if len(raw_text.encode("utf-8")) > 16 * 1024:
            await self._send_error(
                websocket,
                code="control_message_too_large",
                message="控制消息超过允许大小。",
                recoverable=False,
            )
            return _ClientMessageResult.fatal_result(
                provider_session, None, None, started, finishing, audio_bytes,
                close_code=1009,
                close_reason="Control message too large",
            )
        try:
            control = json.loads(raw_text)
        except json.JSONDecodeError:
            await self._send_error(
                websocket,
                code="invalid_control_message",
                message="无法识别语音转写控制消息。",
                recoverable=True,
            )
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, finishing, audio_bytes
            )
        if not isinstance(control, dict) or not isinstance(control.get("type"), str):
            await self._send_error(
                websocket,
                code="invalid_control_message",
                message="语音转写控制消息格式无效。",
                recoverable=True,
            )
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, finishing, audio_bytes
            )

        command = control["type"]
        if command == "ping":
            await self._send(websocket, {"type": "pong", "message": "pong"})
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, finishing, audio_bytes
            )
        if command == "get_status":
            await self._send(
                websocket,
                {"type": "status", "message": "Connection is healthy", "started": started},
            )
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, finishing, audio_bytes
            )
        if command == "start_transcription":
            if started and not finishing:
                await self._send_error(
                    websocket,
                    code="transcription_already_started",
                    message="语音转写已经开始。",
                    recoverable=True,
                )
                return _ClientMessageResult.continue_result(
                    provider_session, None, None, started, finishing, audio_bytes
                )
            audio_format = self._resolve_audio_format(control)
            if audio_format is None:
                await self._send_error(
                    websocket,
                    code="unsupported_audio_format",
                    message="仅支持 PCM 16-bit、16kHz、单声道音频。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1003,
                    close_reason="Unsupported audio format",
                )
            try:
                new_session = await self._provider.create_session(audio_format)
            except (SpeechProviderProtocolError, SpeechProviderUnavailableError):
                await self._send_error(
                    websocket,
                    code="speech_provider_unavailable",
                    message="语音转写服务暂时不可用，请稍后重试。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1011,
                    close_reason="Speech provider unavailable",
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._send_error(
                    websocket,
                    code="speech_provider_unavailable",
                    message="语音转写服务暂时不可用，请稍后重试。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1011,
                    close_reason="Speech provider unavailable",
                )
            iterator = new_session.events()
            event_task = asyncio.create_task(_next_provider_event(iterator))
            await self._send(
                websocket,
                {"type": "transcription_started", "message": "Transcription started"},
            )
            return _ClientMessageResult.continue_result(
                new_session, iterator, event_task, True, False, 0
            )
        if command == "stop_transcription":
            if not started or provider_session is None:
                await self._send_error(
                    websocket,
                    code="transcription_not_started",
                    message="当前没有正在进行的语音转写。",
                    recoverable=True,
                )
                return _ClientMessageResult.continue_result(
                    provider_session, None, None, started, finishing, audio_bytes
                )
            if finishing:
                await self._send(
                    websocket,
                    {
                        "type": "transcription_stopping",
                        "message": "Transcription is stopping",
                    },
                )
                return _ClientMessageResult.continue_result(
                    provider_session, None, None, started, finishing, audio_bytes
                )
            try:
                await provider_session.finish()
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._send_error(
                    websocket,
                    code="speech_provider_failed",
                    message="语音转写服务暂时不可用，请稍后重试。",
                    recoverable=False,
                )
                return _ClientMessageResult.fatal_result(
                    provider_session, None, None, started, finishing, audio_bytes,
                    close_code=1011,
                    close_reason="Speech provider finish failure",
                )
            await self._send(
                websocket,
                {
                    "type": "transcription_stopping",
                    "message": "Transcription is stopping",
                },
            )
            return _ClientMessageResult.continue_result(
                provider_session, None, None, started, True, audio_bytes
            )

        await self._send_error(
            websocket,
            code="unknown_command",
            message="无法识别语音转写控制指令。",
            recoverable=True,
        )
        return _ClientMessageResult.continue_result(
            provider_session, None, None, started, finishing, audio_bytes
        )

    def _resolve_audio_format(self, control: dict[str, Any]) -> SpeechAudioFormat | None:
        nested = control.get("audio_format") or control.get("audioFormat")
        values = nested if isinstance(nested, dict) else control
        encoding = (
            values.get("encoding")
            or values.get("format")
            or self._settings.asr_audio_format
        )
        sample_rate = (
            values.get("sample_rate")
            or values.get("sampleRate")
            or self._settings.asr_sample_rate
        )
        channels = values.get("channels") or self._settings.asr_channels
        if (
            not isinstance(encoding, str)
            or not isinstance(sample_rate, int)
            or not isinstance(channels, int)
        ):
            return None
        expected = SpeechAudioFormat(
            encoding=self._settings.asr_audio_format,
            sample_rate=self._settings.asr_sample_rate,
            channels=self._settings.asr_channels,
        )
        return expected if SpeechAudioFormat(encoding, sample_rate, channels) == expected else None

    async def _send_provider_event(
        self, websocket: WebSocket, event: SpeechRecognitionEvent
    ) -> bool:
        return await self._send(
            websocket,
            {
                "type": "final" if event.status == "final" else "transcription",
                "message": (
                    "Transcription completed"
                    if event.status == "final"
                    else "Partial snapshot"
                ),
                "data": event.text,
                "fullText": event.text,
                "isSnapshot": True,
                "updateAction": "archive" if event.status == "final" else "replace",
                "revision": event.revision,
                "resultStatus": event.status,
                "segmentId": event.segment_id,
            },
        )

    async def _send_error(
        self,
        websocket: WebSocket,
        *,
        code: str,
        message: str,
        recoverable: bool,
    ) -> bool:
        return await self._send(
            websocket,
            {
                "type": "error",
                "code": code,
                "message": message,
                "recoverable": recoverable,
                "severity": "recoverable" if recoverable else "fatal",
            },
        )

    async def _send(self, websocket: WebSocket, payload: dict[str, Any]) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            return False

    async def _close(self, websocket: WebSocket, code: int, reason: str) -> None:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await websocket.close(code=code, reason=reason)


async def _next_provider_event(iterator: Any) -> SpeechRecognitionEvent | None:
    try:
        event = await iterator.__anext__()
    except StopAsyncIteration:
        return None
    if event is None or isinstance(event, SpeechRecognitionEvent):
        return event
    raise TypeError("Speech provider returned an invalid event")


@dataclass(frozen=True, slots=True)
class _ClientMessageResult:
    provider_session: SpeechToTextSession | None
    provider_iterator: Any
    provider_event_task: asyncio.Task[SpeechRecognitionEvent | None] | None
    started: bool
    finishing: bool
    audio_bytes: int
    stop: bool = False
    fatal: bool = False
    close_code: int = 1000
    close_reason: str = "Completed"

    @classmethod
    def continue_result(
        cls,
        provider_session: SpeechToTextSession | None,
        provider_iterator: Any,
        provider_event_task: asyncio.Task[SpeechRecognitionEvent | None] | None,
        started: bool,
        finishing: bool,
        audio_bytes: int,
    ) -> _ClientMessageResult:
        return cls(
            provider_session,
            provider_iterator,
            provider_event_task,
            started,
            finishing,
            audio_bytes,
        )

    @classmethod
    def stop_result(
        cls,
        provider_session: SpeechToTextSession | None,
        provider_iterator: Any,
        provider_event_task: asyncio.Task[SpeechRecognitionEvent | None] | None,
        started: bool,
        finishing: bool,
        audio_bytes: int,
    ) -> _ClientMessageResult:
        return cls(
            provider_session,
            provider_iterator,
            provider_event_task,
            started,
            finishing,
            audio_bytes,
            stop=True,
        )

    @classmethod
    def fatal_result(
        cls,
        provider_session: SpeechToTextSession | None,
        provider_iterator: Any,
        provider_event_task: asyncio.Task[SpeechRecognitionEvent | None] | None,
        started: bool,
        finishing: bool,
        audio_bytes: int,
        *,
        close_code: int,
        close_reason: str,
    ) -> _ClientMessageResult:
        return cls(
            provider_session,
            provider_iterator,
            provider_event_task,
            started,
            finishing,
            audio_bytes,
            stop=True,
            fatal=True,
            close_code=close_code,
            close_reason=close_reason,
        )
