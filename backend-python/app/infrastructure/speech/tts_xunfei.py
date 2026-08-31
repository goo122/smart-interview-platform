"""Server-side adapter for the Xunfei long-text TTS HTTP protocol."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.modules.speech.tts_exceptions import (
    TextToSpeechProviderError,
    TextToSpeechProviderUnavailable,
)
from app.modules.speech.tts_ports import TextToSpeechRequest, TextToSpeechResult

DEFAULT_XUNFEI_TTS_URL = "https://api-dx.xf-yun.com/v1/private/dts_create"


class XunfeiTextToSpeechAdapter:
    provider_name = "xunfei"
    # Long-text DTS accepts lame encoding and returns an MP3-compatible stream.
    supported_audio_formats = ("lame",)
    supported_voices = ("x4_mingge",)
    max_text_length = 100000
    supports_streaming = False

    def __init__(
        self,
        *,
        app_id: str | None,
        api_key: str | None,
        api_secret: str | None,
        endpoint: str = DEFAULT_XUNFEI_TTS_URL,
        max_audio_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self._app_id = app_id.strip() if app_id else ""
        self._api_key = api_key.strip() if api_key else ""
        self._api_secret = api_secret.strip() if api_secret else ""
        self._endpoint = endpoint.strip() or DEFAULT_XUNFEI_TTS_URL
        self._max_audio_bytes = max_audio_bytes
        self.is_available = bool(self._app_id and self._api_key and self._api_secret)

    async def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        if not self.is_available:
            raise TextToSpeechProviderUnavailable("Text-to-speech provider is not configured")

        query_endpoint = self._endpoint.replace("dts_create", "dts_query", 1)
        timeout = httpx.Timeout(request.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                sid, task_id = await self._create(client, request)
                audio_url: str | None = None
                status = 1
                while status in {1, 3}:
                    await asyncio.sleep(request.poll_interval_seconds)
                    status, audio_url = await self._query(client, query_endpoint, task_id, sid)
                if status != 5 or not audio_url:
                    raise TextToSpeechProviderError("Xunfei TTS did not complete")
                audio_bytes = await self._download_audio(client, audio_url)
        except asyncio.CancelledError:
            raise
        except TextToSpeechProviderError:
            raise
        except (httpx.HTTPError, TimeoutError) as exc:
            raise TextToSpeechProviderUnavailable("Xunfei TTS is unavailable") from exc
        except Exception as exc:
            raise TextToSpeechProviderError("Xunfei TTS failed") from exc

        return TextToSpeechResult(
            audio_bytes=audio_bytes,
            audio_format="mp3" if request.audio_format == "lame" else request.audio_format,
            content_type="audio/mpeg" if request.audio_format in {"lame", "mp3"} else "audio/wav",
        )

    async def _create(
        self, client: httpx.AsyncClient, request: TextToSpeechRequest
    ) -> tuple[str, str]:
        body = {
            "header": {"app_id": self._app_id},
            "parameter": {
                "dts": {
                    "vcn": request.voice,
                    "language": request.language,
                    "speed": request.speed,
                    "volume": request.volume,
                    "pitch": request.pitch,
                    "rhy": request.rhythm,
                    "audio": {
                        "encoding": request.audio_format,
                        "sample_rate": request.sample_rate,
                    },
                    "pybuf": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                    },
                }
            },
            "payload": {
                "text": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain",
                    "text": _b64(request.text),
                }
            },
        }
        signed_endpoint, headers = self._signed_request("POST", self._endpoint)
        response = await client.post(signed_endpoint, headers=headers, json=body)
        payload = _json_object(response)
        _ensure_provider_success(payload)
        header = _object(payload.get("header"))
        sid = _string(header.get("sid"))
        task_id = _string(header.get("task_id"))
        if not sid or not task_id:
            raise TextToSpeechProviderError("Invalid Xunfei TTS create response")
        return sid, task_id

    async def _query(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        task_id: str,
        sid: str,
    ) -> tuple[int, str | None]:
        body = {"header": {"app_id": self._app_id, "task_id": task_id, "sid": sid}}
        signed_endpoint, headers = self._signed_request("POST", endpoint)
        response = await client.post(signed_endpoint, headers=headers, json=body)
        payload = _json_object(response)
        _ensure_provider_success(payload)
        header = _object(payload.get("header"))
        status = _integer(header.get("task_status"))
        if status is None:
            raise TextToSpeechProviderError("Invalid Xunfei TTS task status")
        data = _object(payload.get("payload"))
        audio = _object(data.get("audio"))
        return status, _decode_provider_url(audio.get("audio"))

    async def _download_audio(self, client: httpx.AsyncClient, audio_url: str) -> bytes:
        parsed = urlparse(audio_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise TextToSpeechProviderError("Invalid Xunfei audio URL")
        chunks: list[bytes] = []
        async with client.stream("GET", audio_url) as response:
            if response.status_code >= 400:
                raise TextToSpeechProviderUnavailable("Xunfei audio download failed")
            content_length = response.headers.get("Content-Length")
            if (
                content_length
                and content_length.isdigit()
                and int(content_length) > self._max_audio_bytes
            ):
                raise TextToSpeechProviderError("Xunfei audio is too large")
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > self._max_audio_bytes:
                    raise TextToSpeechProviderError("Xunfei audio is too large")
                chunks.append(chunk)
        return b"".join(chunks)

    def _signed_request(self, method: str, endpoint: str) -> tuple[str, dict[str, str]]:
        parsed = urlparse(endpoint)
        host = parsed.netloc
        request_line = f"{method} {parsed.path or '/'} HTTP/1.1"
        date = format_datetime(datetime.now(UTC), usegmt=True)
        signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
        digest = hmac.new(
            self._api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = base64.b64encode(digest).decode("ascii")
        authorization_origin = (
            f'api_key="{self._api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
        query = parse_qsl(parsed.query, keep_blank_values=True)
        query.extend(
            (
                ("host", host),
                ("date", date),
                ("authorization", authorization),
            )
        )
        signed_endpoint = urlunparse(parsed._replace(query=urlencode(query)))
        return signed_endpoint, {
            "Authorization": authorization,
            "Date": date,
            "x-date": date,
            "Host": host,
            "Content-Type": "application/json",
        }


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _json_object(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise TextToSpeechProviderUnavailable("Xunfei TTS request failed")
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise TextToSpeechProviderError("Invalid Xunfei TTS response") from exc
    if not isinstance(payload, dict):
        raise TextToSpeechProviderError("Invalid Xunfei TTS response")
    return payload


def _ensure_provider_success(payload: dict[str, Any]) -> None:
    header = _object(payload.get("header"))
    code = _integer(header.get("code"))
    if code != 0:
        raise TextToSpeechProviderError("Xunfei TTS rejected the request")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _decode_provider_url(value: Any) -> str | None:
    raw = _string(value)
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw).decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError):
        return raw
    return decoded if decoded.startswith(("https://", "http://")) else raw


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
