"""Server-side adapter for the Xunfei IAT WebSocket protocol.

Only this module knows the provider URL, signing algorithm and response shape.
The application service receives provider-neutral snapshots from ``ports.py``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import quote, urlparse

from app.modules.speech.exceptions import (
    SpeechProviderProtocolError,
    SpeechProviderUnavailableError,
)
from app.modules.speech.ports import (
    SpeechAudioFormat,
    SpeechRecognitionEvent,
    SpeechToTextSession,
)

DEFAULT_XUNFEI_ASR_URL = "wss://iat-api.xfyun.cn/v2/iat"


class XunfeiSpeechToTextAdapter:
    provider_name = "xunfei"
    is_available = True

    def __init__(
        self,
        *,
        app_id: str | None,
        api_key: str | None,
        api_secret: str | None,
        endpoint: str = DEFAULT_XUNFEI_ASR_URL,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._app_id = app_id.strip() if app_id else ""
        self._api_key = api_key.strip() if api_key else ""
        self._api_secret = api_secret.strip() if api_secret else ""
        self._endpoint = endpoint.strip() or DEFAULT_XUNFEI_ASR_URL
        self._timeout_seconds = timeout_seconds
        self.is_available = bool(self._app_id and self._api_key and self._api_secret)

    @property
    def supported_audio_formats(self) -> Sequence[str]:
        return ("pcm_s16le",)

    async def create_session(self, audio_format: SpeechAudioFormat) -> SpeechToTextSession:
        if not self.is_available:
            raise SpeechProviderUnavailableError("Speech-to-text provider is not configured")
        if audio_format.encoding != "pcm_s16le":
            raise SpeechProviderProtocolError("Unsupported speech audio format")

        try:
            from websockets.asyncio.client import connect

            connection = await connect(
                _build_signed_url(
                    self._endpoint,
                    self._app_id,
                    self._api_key,
                    self._api_secret,
                ),
                open_timeout=self._timeout_seconds,
                close_timeout=5,
                max_size=2 * 1024 * 1024,
            )
        except ImportError as exc:
            raise SpeechProviderUnavailableError("Speech-to-text provider is unavailable") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise SpeechProviderUnavailableError("Speech-to-text provider is unavailable") from exc

        return XunfeiSpeechToTextSession(
            connection=connection,
            app_id=self._app_id,
            audio_format=audio_format,
        )


class XunfeiSpeechToTextSession:
    def __init__(self, *, connection: Any, app_id: str, audio_format: SpeechAudioFormat) -> None:
        self._connection = connection
        self._app_id = app_id
        self._audio_format = audio_format
        self._started = False
        self._finished = False
        self._closed = False
        self._revision = 0
        self._assembler = _XunfeiTranscriptAssembler()

    async def send_audio(self, audio: bytes) -> None:
        if self._closed or self._finished or not audio:
            return
        if len(audio) % 2 != 0:
            raise SpeechProviderProtocolError("PCM frame must contain complete 16-bit samples")

        payload: dict[str, Any] = {
            "data": {
                "status": 0 if not self._started else 1,
                "format": f"audio/L16;rate={self._audio_format.sample_rate}",
                "encoding": "raw",
                "audio": base64.b64encode(audio).decode("ascii"),
            }
        }
        if not self._started:
            payload["common"] = {"app_id": self._app_id}
            payload["business"] = {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "dwa": "wpgs",
                "vad_eos": 5000,
            }
            self._started = True
        await self._connection.send(json.dumps(payload, ensure_ascii=False))

    async def finish(self) -> None:
        if self._closed or self._finished:
            return
        self._finished = True
        payload: dict[str, Any] = {
            "data": {
                "status": 2,
                "format": f"audio/L16;rate={self._audio_format.sample_rate}",
                "encoding": "raw",
                "audio": "",
            }
        }
        if not self._started:
            payload["common"] = {"app_id": self._app_id}
            payload["business"] = {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "dwa": "wpgs",
                "vad_eos": 5000,
            }
            self._started = True
        await self._connection.send(json.dumps(payload, ensure_ascii=False))

    async def _read_events(self) -> AsyncIterator[SpeechRecognitionEvent | None]:
        try:
            async for raw_message in self._connection:
                event = self._parse_message(raw_message)
                if event is not None:
                    yield event
                    if event.status == "final":
                        return
        except asyncio.CancelledError:
            raise
        except SpeechProviderProtocolError:
            raise
        except Exception as exc:
            raise SpeechProviderUnavailableError("Speech-to-text provider is unavailable") from exc
        finally:
            yield None

    def events(self) -> AsyncIterator[SpeechRecognitionEvent | None]:
        return self._read_events()

    def _parse_message(self, raw_message: Any) -> SpeechRecognitionEvent | None:
        if not isinstance(raw_message, str):
            raise SpeechProviderProtocolError("Invalid speech provider response")
        try:
            payload = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError) as exc:
            raise SpeechProviderProtocolError("Invalid speech provider response") from exc
        if not isinstance(payload, dict):
            raise SpeechProviderProtocolError("Invalid speech provider response")

        code = _as_int(payload.get("code"), default=0)
        if code != 0:
            raise SpeechProviderProtocolError("Speech provider rejected the audio")

        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        result = data.get("result")
        if not isinstance(result, dict):
            return None

        text_payload = result.get("text")
        decoded_text = _decode_result_text(text_payload)
        pgs = decoded_text.get("pgs")
        segment_id = _as_int(decoded_text.get("sn"))
        replace_range = _as_range(decoded_text.get("rg"))
        segment_text = _extract_segment_text(decoded_text)
        snapshot_changed = self._assembler.apply(
            segment_id=segment_id,
            pgs=pgs if isinstance(pgs, str) else None,
            replace_range=replace_range,
            text=segment_text,
        )
        result_status = _as_int(data.get("status"), default=_as_int(result.get("status")))
        is_final = result_status == 2
        if not snapshot_changed and not is_final:
            return None

        self._revision += 1
        return SpeechRecognitionEvent(
            text=self._assembler.snapshot,
            status="final" if is_final else "partial",
            revision=self._revision,
            segment_id=segment_id,
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._connection.close()
        except Exception:
            return


class _XunfeiTranscriptAssembler:
    def __init__(self) -> None:
        self._segments: dict[int, str] = {}
        self._seen_packets: set[tuple[int | None, str | None, tuple[int, int] | None, str]] = set()
        self.snapshot = ""

    def apply(
        self,
        *,
        segment_id: int | None,
        pgs: str | None,
        replace_range: tuple[int, int] | None,
        text: str,
    ) -> bool:
        packet_key = (segment_id, pgs, replace_range, text)
        if packet_key in self._seen_packets:
            return False
        self._seen_packets.add(packet_key)

        resolved_segment_id = segment_id if segment_id is not None else self._next_segment_id()
        if pgs == "rpl" and replace_range is not None:
            start, end = replace_range
            for item in range(max(0, start - 1), end):
                self._segments.pop(item, None)
        self._segments[resolved_segment_id] = text
        next_snapshot = "".join(self._segments[index] for index in sorted(self._segments))
        changed = next_snapshot != self.snapshot
        self.snapshot = next_snapshot
        return changed

    def _next_segment_id(self) -> int:
        return max(self._segments, default=-1) + 1


def _build_signed_url(endpoint: str, app_id: str, api_key: str, api_secret: str) -> str:
    parsed = urlparse(endpoint)
    host = parsed.netloc
    request_line = f"GET {parsed.path or '/'} HTTP/1.1"
    date = format_datetime(datetime.now(UTC), usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
    digest = hmac.new(
        api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = base64.b64encode(digest).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    separator = "&" if parsed.query else "?"
    return (
        f"{endpoint}{separator}authorization={quote(authorization)}"
        f"&date={quote(date)}&host={quote(host)}"
    )


def _decode_result_text(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        decoded = base64.b64decode(value).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpeechProviderProtocolError("Invalid speech provider response") from exc
    if not isinstance(payload, dict):
        raise SpeechProviderProtocolError("Invalid speech provider response")
    return payload


def _extract_segment_text(payload: dict[str, Any]) -> str:
    words = payload.get("ws")
    if not isinstance(words, list):
        return ""
    parts: list[str] = []
    for word in words:
        if not isinstance(word, dict):
            continue
        candidates = word.get("cw")
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if isinstance(candidate, dict) and isinstance(candidate.get("w"), str):
                parts.append(candidate["w"])
    return "".join(parts)


def _as_int(value: Any, default: int | None = None) -> int | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    start = _as_int(value[0])
    end = _as_int(value[1])
    if start is None or end is None:
        return None
    return (min(start, end), max(start, end))
