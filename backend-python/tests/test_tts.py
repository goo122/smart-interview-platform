import asyncio
import base64
import io
import time
import wave
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.infrastructure.speech.tts_fake import FakeTextToSpeechAdapter
from app.infrastructure.speech.tts_xunfei import (
    XunfeiTextToSpeechAdapter,
    _decode_provider_url,
)
from app.main import app
from app.modules.speech.tts_exceptions import (
    TextToSpeechFailedError,
    TextToSpeechProviderError,
    TextToSpeechUnavailableError,
)
from app.modules.speech.tts_factory import TextToSpeechProviderFactory
from app.modules.speech.tts_ports import TextToSpeechRequest, TextToSpeechResult
from app.modules.speech.tts_service import TextToSpeechService


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "text_to_speech_provider": "fake",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def tts_client(auth_client) -> Iterator[tuple[TestClient, FakeTextToSpeechAdapter]]:
    client, _, _ = auth_client
    provider = FakeTextToSpeechAdapter()
    original_service = getattr(app.state, "text_to_speech_service", None)
    app.state.text_to_speech_service = TextToSpeechService(provider, _settings())
    try:
        yield client, provider
    finally:
        if original_service is None:
            delattr(app.state, "text_to_speech_service")
        else:
            app.state.text_to_speech_service = original_service


def _login(client: TestClient, *, username: str = "tts-user") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "secure-password",
        },
    )
    assert response.status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        json={"account": f"{username}@example.com", "password": "secure-password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_tts_requires_authentication(tts_client) -> None:
    client, _ = tts_client
    response = client.post(
        "/api/xunzhi/v1/xunfei/tts/synthesize",
        json={"text": "需要登录"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_fake_provider_returns_browser_playable_wav(tts_client) -> None:
    client, provider = tts_client
    token = _login(client)
    response = client.post(
        "/api/xunzhi/v1/xunfei/tts/synthesize",
        headers=_headers(token),
        json={"text": "你好，面试开始。", "audioEncoding": "lame"},
    )
    assert response.status_code == 200
    payload = response.json()
    audio = base64.b64decode(payload["audioBase64"])
    with wave.open(io.BytesIO(audio), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
        assert wav.getnframes() > 0
    assert payload["audioFormat"] == "wav"
    assert payload["contentType"] == "audio/wav"
    assert payload["audioUrl"] is None
    assert response.headers["cache-control"] == "no-store"
    assert provider.calls == 1


def test_empty_and_overlong_text_are_rejected(tts_client) -> None:
    client, _ = tts_client
    token = _login(client)
    empty = client.post(
        "/api/xunzhi/v1/xunfei/tts/synthesize",
        headers=_headers(token),
        json={"text": "   "},
    )
    too_long = client.post(
        "/api/xunzhi/v1/xunfei/tts/synthesize",
        headers=_headers(token),
        json={"text": "a" * 10001},
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "invalid_tts_request"
    assert too_long.status_code == 400
    assert too_long.json()["error"]["code"] == "invalid_tts_request"


def test_unsupported_format_and_voice_are_rejected(tts_client) -> None:
    client, _ = tts_client
    token = _login(client)
    for payload in (
        {"text": "测试", "audioEncoding": "ogg"},
        {"text": "测试", "vcn": "unknown-voice"},
    ):
        response = client.post(
            "/api/xunzhi/v1/xunfei/tts/synthesize",
            headers=_headers(token),
            json=payload,
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_tts_request"


def test_unavailable_provider_returns_safe_error(auth_client) -> None:
    client, _, _ = auth_client
    original_service = getattr(app.state, "text_to_speech_service", None)
    settings = _settings(text_to_speech_provider="unavailable")
    from app.infrastructure.speech.tts_unavailable import UnavailableTextToSpeechAdapter

    app.state.text_to_speech_service = TextToSpeechService(
        UnavailableTextToSpeechAdapter(), settings
    )
    try:
        token = _login(client, username="tts-unavailable-user")
        response = client.post(
            "/api/xunzhi/v1/xunfei/tts/synthesize",
            headers=_headers(token),
            json={"text": "不会调用真实 Provider"},
        )
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "tts_provider_unavailable"
        assert "api" not in str(body).lower()
    finally:
        if original_service is None:
            delattr(app.state, "text_to_speech_service")
        else:
            app.state.text_to_speech_service = original_service


def test_task_endpoint_checks_user_ownership_and_expiry(auth_client) -> None:
    client, _, _ = auth_client
    original_service = getattr(app.state, "text_to_speech_service", None)
    provider = FakeTextToSpeechAdapter()
    app.state.text_to_speech_service = TextToSpeechService(
        provider, _settings(tts_task_ttl_seconds=1)
    )
    try:
        first_token = _login(client, username="tts-task-owner")
        second_token = _login(client, username="tts-task-other")
        response = client.post(
            "/api/xunzhi/v1/xunfei/tts/tasks",
            headers=_headers(first_token),
            json={"text": "短期任务"},
        )
        assert response.status_code == 200
        task_id = response.json()["taskId"]
        assert UUID(task_id)
        assert (
            client.get(
                f"/api/xunzhi/v1/xunfei/tts/tasks/{task_id}",
                headers=_headers(second_token),
            ).status_code
            == 404
        )
        time.sleep(1.1)
        assert (
            client.get(
                f"/api/xunzhi/v1/xunfei/tts/tasks/{task_id}",
                headers=_headers(first_token),
            ).status_code
            == 404
        )
    finally:
        if original_service is None:
            delattr(app.state, "text_to_speech_service")
        else:
            app.state.text_to_speech_service = original_service


def test_idempotent_request_does_not_call_provider_twice(tts_client) -> None:
    client, provider = tts_client
    token = _login(client, username="tts-idempotent-user")
    payload = {"text": "只合成一次", "requestId": "tts-request-1"}
    first = client.post(
        "/api/xunzhi/v1/xunfei/tts/synthesize",
        headers=_headers(token),
        json=payload,
    )
    second = client.post(
        "/api/xunzhi/v1/xunfei/tts/synthesize",
        headers=_headers(token),
        json=payload,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["taskId"] == second.json()["taskId"]
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_concurrent_idempotent_requests_share_one_provider_call() -> None:
    provider = FakeTextToSpeechAdapter()
    service = TextToSpeechService(provider, _settings())
    user_id = uuid4()
    from app.modules.speech.tts_schemas import TextToSpeechRequestSchema

    payload = TextToSpeechRequestSchema(text="并发只合成一次", requestId="concurrent-1")
    records = await asyncio.gather(
        service.synthesize(user_id, payload),
        service.synthesize(user_id, payload),
    )
    assert records[0].task_id == records[1].task_id
    assert provider.calls == 1


def test_capabilities_are_authenticated_and_secret_free(tts_client) -> None:
    client, _ = tts_client
    assert client.get("/api/xunzhi/v1/speech/tts/capabilities").status_code == 401
    token = _login(client, username="tts-capabilities-user")
    response = client.get(
        "/api/xunzhi/v1/speech/tts/capabilities",
        headers=_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "available": True,
        "provider": "fake",
        "supportedAudioFormats": ["wav", "mp3", "lame"],
        "supportedVoices": ["x4_mingge"],
        "maxTextLength": 10000,
        "supportsStreaming": False,
    }
    assert "api_key" not in str(payload)
    assert "api_secret" not in str(payload)


def test_fake_provider_is_rejected_in_production() -> None:
    with pytest.raises(ValueError):
        _settings(app_env="production")
    settings = _settings()
    settings.app_env = "production"
    with pytest.raises(RuntimeError):
        TextToSpeechProviderFactory.build(settings)


def test_xunfei_signing_keeps_query_and_headers_consistent() -> None:
    adapter = XunfeiTextToSpeechAdapter(
        app_id="test-app",
        api_key="test-key",
        api_secret="test-secret",
        endpoint="https://api-dx.xf-yun.com/v1/private/dts_create",
    )
    signed_url, headers = adapter._signed_request(  # noqa: SLF001
        "POST", "https://api-dx.xf-yun.com/v1/private/dts_create"
    )
    query = parse_qs(urlparse(signed_url).query)
    assert query["host"] == ["api-dx.xf-yun.com"]
    assert query["date"]
    assert query["authorization"] == [headers["Authorization"]]
    assert headers["Date"] == headers["x-date"]


def test_xunfei_audio_url_is_decoded_server_side() -> None:
    encoded = base64.b64encode(b"https://cdn.xf-yun.com/audio.mp3").decode("ascii")
    assert _decode_provider_url(encoded) == "https://cdn.xf-yun.com/audio.mp3"
    encoded_http = base64.b64encode(b"http://sgw-dx.xf-yun.com/audio.mp3").decode("ascii")
    assert _decode_provider_url(encoded_http) == "http://sgw-dx.xf-yun.com/audio.mp3"


@pytest.mark.asyncio
async def test_xunfei_query_omits_sid_field() -> None:
    class RecordingClient:
        def __init__(self) -> None:
            self.body: dict[str, object] | None = None

        async def post(self, _url: str, **kwargs: object) -> httpx.Response:
            body = kwargs.get("json")
            assert isinstance(body, dict)
            self.body = body
            return httpx.Response(
                200,
                json={
                    "header": {"code": 0, "task_status": 5},
                    "payload": {
                        "audio": {
                            "audio": base64.b64encode(
                                b"https://cdn.xf-yun.com/audio.mp3"
                            ).decode("ascii")
                        }
                    },
                },
            )

    client = RecordingClient()
    adapter = XunfeiTextToSpeechAdapter(
        app_id="test-app",
        api_key="test-key",
        api_secret="test-secret",
    )

    status, audio_url = await adapter._query(  # noqa: SLF001
        client, "https://api-dx.xf-yun.com/v1/private/dts_query", "task-id"
    )

    assert status == 5
    assert audio_url == "https://cdn.xf-yun.com/audio.mp3"
    assert client.body == {"header": {"app_id": "test-app", "task_id": "task-id"}}


class BlockingTextToSpeechAdapter:
    provider_name = "fake"
    is_available = True
    supported_audio_formats = ("wav",)
    supported_voices = ("x4_mingge",)
    max_text_length = 10000
    supports_streaming = False

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.released = False

    async def synthesize(self, _request: TextToSpeechRequest) -> TextToSpeechResult:
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.released = True
        raise AssertionError("unreachable")


class FailingTextToSpeechAdapter(BlockingTextToSpeechAdapter):
    async def synthesize(self, _request: TextToSpeechRequest) -> TextToSpeechResult:
        raise TextToSpeechProviderError("secret provider response")


@pytest.mark.asyncio
async def test_provider_cancellation_releases_operation() -> None:
    provider = BlockingTextToSpeechAdapter()
    service = TextToSpeechService(provider, _settings(tts_request_timeout_seconds=10))
    task = asyncio.create_task(
        service.synthesize(uuid4(), _request_payload())
    )
    await provider.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.released is True


@pytest.mark.asyncio
async def test_provider_timeout_releases_operation() -> None:
    provider = BlockingTextToSpeechAdapter()
    service = TextToSpeechService(provider, _settings(tts_request_timeout_seconds=0.01))
    with pytest.raises(TextToSpeechUnavailableError):
        await service.synthesize(uuid4(), _request_payload())
    assert provider.released is True


@pytest.mark.asyncio
async def test_provider_failure_is_safe() -> None:
    service = TextToSpeechService(FailingTextToSpeechAdapter(), _settings())
    with pytest.raises(TextToSpeechFailedError) as error:
        await service.synthesize(uuid4(), _request_payload())
    assert "secret provider response" not in str(error.value)


def _request_payload():
    from app.modules.speech.tts_schemas import TextToSpeechRequestSchema

    return TextToSpeechRequestSchema(text="测试")
