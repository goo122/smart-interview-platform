import asyncio
import base64
import json
import time
from collections.abc import AsyncIterator, Iterator
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.infrastructure.speech.fake import FakeSpeechToTextAdapter
from app.infrastructure.speech.xunfei import XunfeiSpeechToTextSession
from app.main import app
from app.modules.auth.dependencies import get_websocket_user_repository
from app.modules.speech.ports import SpeechAudioFormat, SpeechToTextSession
from app.modules.speech.service import SpeechToTextService


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "test",
        "speech_to_text_provider": "fake",
    }
    values.update(overrides)
    return Settings(**values)


class FailingSpeechToTextAdapter:
    provider_name = "fake"
    is_available = True
    supported_audio_formats = ("pcm_s16le",)

    async def create_session(self, audio_format: SpeechAudioFormat) -> SpeechToTextSession:
        raise RuntimeError("provider response must not reach the client")


class InterruptingSpeechToTextSession:
    def __init__(self) -> None:
        self.closed = False
        self.events_finished = False

    async def send_audio(self, audio: bytes) -> None:
        return

    async def finish(self) -> None:
        return

    async def _events(self) -> AsyncIterator[None]:
        try:
            raise RuntimeError("provider stream interrupted")
        finally:
            self.events_finished = True
        yield None

    def events(self) -> AsyncIterator[None]:
        return self._events()

    async def close(self) -> None:
        self.closed = True


class InterruptingSpeechToTextAdapter:
    provider_name = "fake"
    is_available = True
    supported_audio_formats = ("pcm_s16le",)

    def __init__(self) -> None:
        self.session = InterruptingSpeechToTextSession()

    async def create_session(self, audio_format: SpeechAudioFormat) -> SpeechToTextSession:
        return self.session


class FakeXunfeiConnection:
    def __init__(self, messages: list[str]) -> None:
        self._messages = iter(messages)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._messages)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def close(self) -> None:
        self.closed = True


def _xunfei_result(
    *,
    text: str,
    segment_id: int,
    status: int = 1,
    pgs: str = "apd",
    replace_range: list[int] | None = None,
) -> str:
    result = {
        "sn": segment_id,
        "pgs": pgs,
        "ws": [{"cw": [{"w": text}]}],
    }
    if replace_range is not None:
        result["rg"] = replace_range
    return json.dumps({"code": 0, "data": {"status": status, "result": result}})


def _legacy_xunfei_result(*, text: str, segment_id: int, status: int = 1) -> str:
    result = {
        "sn": segment_id,
        "pgs": "apd",
        "ws": [{"cw": [{"w": text}]}],
    }
    encoded_result = base64.b64encode(json.dumps(result).encode()).decode()
    return json.dumps(
        {"code": 0, "data": {"status": status, "result": {"text": encoded_result}}}
    )


@pytest.fixture
def speech_client(auth_client) -> Iterator[tuple[TestClient, FakeSpeechToTextAdapter]]:
    client, repository, _ = auth_client
    provider = FakeSpeechToTextAdapter(
        partial_texts=("你好", "你好，欢迎使用语音转写"),
        final_text="你好，欢迎使用语音转写。",
    )
    original_service = getattr(app.state, "speech_to_text_service", None)
    app.state.speech_to_text_service = SpeechToTextService(provider, _settings())
    app.dependency_overrides[get_websocket_user_repository] = lambda: repository
    try:
        yield client, provider
    finally:
        if original_service is None:
            delattr(app.state, "speech_to_text_service")
        else:
            app.state.speech_to_text_service = original_service
        app.dependency_overrides.pop(get_websocket_user_repository, None)


def _login(client: TestClient, *, username: str = "speech-user") -> str:
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


def _connect(client: TestClient, token: str, username: str = "speech-user"):
    return client.websocket_connect(
        f"/api/xunzhi/v1/xunfei/audio-to-text/{quote(username)}?token={quote(token)}"
    )


def _connect_with_subprotocol(
    client: TestClient, token: str, username: str = "speech-user"
):
    return client.websocket_connect(
        f"/api/xunzhi/v1/xunfei/audio-to-text/{quote(username)}",
        subprotocols=["xunzhi-auth", token],
    )


def _start(websocket) -> None:
    assert websocket.receive_json()["type"] == "connected"
    websocket.send_json(
        {
            "type": "start_transcription",
            "audio_format": {
                "encoding": "pcm_s16le",
                "sample_rate": 16000,
                "channels": 1,
            },
        }
    )
    assert websocket.receive_json()["type"] == "transcription_started"


def test_websocket_requires_authentication(speech_client) -> None:
    client, _ = speech_client
    with pytest.raises(WebSocketDisconnect) as error, client.websocket_connect(
        "/api/xunzhi/v1/xunfei/audio-to-text/speech-user"
    ):
        pass
    assert error.value.code == 1008


def test_user_cannot_impersonate_another_user(speech_client) -> None:
    client, _ = speech_client
    token = _login(client)
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "other-speech-user",
            "email": "other-speech-user@example.com",
            "password": "secure-password",
        },
    )

    with pytest.raises(WebSocketDisconnect) as error, _connect(
        client, token, "other-speech-user"
    ):
        pass
    assert error.value.code == 1008


def test_websocket_authenticates_with_the_token_subprotocol(speech_client) -> None:
    client, _ = speech_client
    token = _login(client, username="speech-subprotocol-user")
    with _connect_with_subprotocol(client, token, "speech-subprotocol-user") as websocket:
        _start(websocket)
        websocket.send_json({"type": "stop_transcription"})
        assert websocket.receive_json()["type"] == "transcription_stopping"
        assert websocket.receive_json()["type"] == "final"
        assert websocket.receive_json()["type"] == "closed"


def test_fake_provider_emits_incremental_and_final_snapshots(speech_client) -> None:
    client, provider = speech_client
    token = _login(client)
    with _connect(client, token) as websocket:
        _start(websocket)
        websocket.send_bytes(b"\x00\x00" * 320)
        partial = websocket.receive_json()
        assert partial["type"] == "transcription"
        assert partial["data"] == "你好"
        websocket.send_bytes(b"\x00\x00" * 320)
        second_partial = websocket.receive_json()
        assert second_partial["data"] == "你好，欢迎使用语音转写"
        websocket.send_json({"type": "stop_transcription"})
        assert websocket.receive_json()["type"] == "transcription_stopping"
        final = websocket.receive_json()
        assert final["type"] == "final"
        assert final["data"] == "你好，欢迎使用语音转写。"
        assert websocket.receive_json()["type"] == "closed"
    assert provider.sessions[0].closed is True


def test_xunfei_provider_orders_and_deduplicates_transcript_snapshots() -> None:
    connection = FakeXunfeiConnection(
        [
            _xunfei_result(text="世界", segment_id=2),
            _xunfei_result(text="你好", segment_id=1),
            _xunfei_result(text="你好", segment_id=1),
            _xunfei_result(text="世界", segment_id=2, status=2),
        ]
    )
    session = XunfeiSpeechToTextSession(
        connection=connection,
        app_id="test-app",
        audio_format=SpeechAudioFormat(
            encoding="pcm_s16le", sample_rate=16000, channels=1
        ),
    )

    async def collect_events() -> list[tuple[str, str, int]]:
        events: list[tuple[str, str, int]] = []
        async for event in session.events():
            if event is not None:
                events.append((event.status, event.text, event.revision))
        return events

    events = asyncio.run(collect_events())

    assert events == [
        ("partial", "世界", 1),
        ("partial", "你好世界", 2),
        ("final", "你好世界", 3),
    ]


def test_xunfei_provider_applies_official_dynamic_replacement_ranges() -> None:
    connection = FakeXunfeiConnection(
        [
            _xunfei_result(text="你好", segment_id=1),
            _xunfei_result(
                text="您好",
                segment_id=2,
                pgs="rpl",
                replace_range=[1, 1],
                status=2,
            ),
        ]
    )
    session = XunfeiSpeechToTextSession(
        connection=connection,
        app_id="test-app",
        audio_format=SpeechAudioFormat(
            encoding="pcm_s16le", sample_rate=16000, channels=1
        ),
    )

    async def collect_events() -> list[tuple[str, str, int]]:
        events: list[tuple[str, str, int]] = []
        async for event in session.events():
            if event is not None:
                events.append((event.status, event.text, event.revision))
        return events

    assert asyncio.run(collect_events()) == [
        ("partial", "你好", 1),
        ("final", "您好", 2),
    ]


def test_xunfei_provider_keeps_legacy_encoded_result_compatibility() -> None:
    connection = FakeXunfeiConnection(
        [_legacy_xunfei_result(text="兼容结果", segment_id=1, status=2)]
    )
    session = XunfeiSpeechToTextSession(
        connection=connection,
        app_id="test-app",
        audio_format=SpeechAudioFormat(
            encoding="pcm_s16le", sample_rate=16000, channels=1
        ),
    )

    async def collect_events() -> list[tuple[str, str, int]]:
        events: list[tuple[str, str, int]] = []
        async for event in session.events():
            if event is not None:
                events.append((event.status, event.text, event.revision))
        return events

    assert asyncio.run(collect_events()) == [("final", "兼容结果", 1)]


def test_unsupported_audio_format_is_rejected(speech_client) -> None:
    client, _ = speech_client
    token = _login(client)
    with _connect(client, token) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "start_transcription",
                "audio_format": {
                    "encoding": "audio/webm",
                    "sample_rate": 48000,
                    "channels": 2,
                },
            }
        )
        error = websocket.receive_json()
        assert error["code"] == "unsupported_audio_format"
        assert error["severity"] == "fatal"
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()


def test_single_frame_and_total_audio_limits_are_enforced(auth_client) -> None:
    client, repository, _ = auth_client
    provider = FakeSpeechToTextAdapter()
    original_service = getattr(app.state, "speech_to_text_service", None)
    app.state.speech_to_text_service = SpeechToTextService(
        provider,
        _settings(asr_max_frame_bytes=4, asr_max_audio_bytes=6),
    )
    app.dependency_overrides[get_websocket_user_repository] = lambda: repository
    try:
        token = _login(client, username="speech-limit-user")
        with _connect(client, token, "speech-limit-user") as websocket:
            _start(websocket)
            websocket.send_bytes(b"\x00\x00" * 3)
            assert websocket.receive_json()["code"] == "audio_frame_too_large"

        with _connect(client, token, "speech-limit-user") as websocket:
            _start(websocket)
            websocket.send_bytes(b"\x00\x00" * 2)
            websocket.send_bytes(b"\x00\x00" * 2)
            assert websocket.receive_json()["type"] == "transcription"
            websocket.send_bytes(b"\x00\x00" * 1)
            assert websocket.receive_json()["code"] == "audio_limit_exceeded"
    finally:
        if original_service is None:
            delattr(app.state, "speech_to_text_service")
        else:
            app.state.speech_to_text_service = original_service
        app.dependency_overrides.pop(get_websocket_user_repository, None)


def test_session_timeout_closes_safely(auth_client) -> None:
    client, repository, _ = auth_client
    provider = FakeSpeechToTextAdapter()
    original_service = getattr(app.state, "speech_to_text_service", None)
    app.state.speech_to_text_service = SpeechToTextService(
        provider,
        _settings(asr_max_session_seconds=1),
    )
    app.dependency_overrides[get_websocket_user_repository] = lambda: repository
    try:
        token = _login(client, username="speech-timeout-user")
        with _connect(client, token, "speech-timeout-user") as websocket:
            assert websocket.receive_json()["type"] == "connected"
            time.sleep(1.1)
            error = websocket.receive_json()
            assert error["code"] == "speech_session_timeout"
            assert error["message"] == "语音转写会话已超时，请重新开始录音。"
    finally:
        if original_service is None:
            delattr(app.state, "speech_to_text_service")
        else:
            app.state.speech_to_text_service = original_service
        app.dependency_overrides.pop(get_websocket_user_repository, None)


def test_provider_failure_is_not_leaked_to_client(auth_client) -> None:
    client, repository, _ = auth_client
    original_service = getattr(app.state, "speech_to_text_service", None)
    app.state.speech_to_text_service = SpeechToTextService(
        FailingSpeechToTextAdapter(),
        _settings(),
    )
    app.dependency_overrides[get_websocket_user_repository] = lambda: repository
    try:
        token = _login(client, username="speech-provider-failure-user")
        with _connect(client, token, "speech-provider-failure-user") as websocket:
            assert websocket.receive_json()["type"] == "connected"
            websocket.send_json({"type": "start_transcription"})
            error = websocket.receive_json()
            assert error["code"] == "speech_provider_unavailable"
            assert error["message"] == "语音转写服务暂时不可用，请稍后重试。"
            assert "provider response" not in str(error)
    finally:
        if original_service is None:
            delattr(app.state, "speech_to_text_service")
        else:
            app.state.speech_to_text_service = original_service
        app.dependency_overrides.pop(get_websocket_user_repository, None)


def test_provider_interruption_releases_background_session(auth_client) -> None:
    client, repository, _ = auth_client
    provider = InterruptingSpeechToTextAdapter()
    original_service = getattr(app.state, "speech_to_text_service", None)
    app.state.speech_to_text_service = SpeechToTextService(provider, _settings())
    app.dependency_overrides[get_websocket_user_repository] = lambda: repository
    try:
        token = _login(client, username="speech-provider-interruption-user")
        with _connect(client, token, "speech-provider-interruption-user") as websocket:
            assert websocket.receive_json()["type"] == "connected"
            websocket.send_json({"type": "start_transcription"})
            assert websocket.receive_json()["type"] == "transcription_started"
            error = websocket.receive_json()
            assert error["code"] == "speech_provider_failed"
            assert error["message"] == "语音转写服务暂时不可用，请稍后重试。"
    finally:
        if original_service is None:
            delattr(app.state, "speech_to_text_service")
        else:
            app.state.speech_to_text_service = original_service
        app.dependency_overrides.pop(get_websocket_user_repository, None)
    assert provider.session.events_finished is True
    assert provider.session.closed is True


def test_client_disconnect_releases_provider_session(speech_client) -> None:
    client, provider = speech_client
    token = _login(client)
    websocket = _connect(client, token)
    websocket.__enter__()
    try:
        _start(websocket)
        websocket.close()
    finally:
        websocket.__exit__(None, None, None)
    assert provider.sessions[0].closed is True


def test_fake_provider_is_rejected_in_production() -> None:
    with pytest.raises(ValueError):
        _settings(app_env="production")


def test_capabilities_are_authenticated_and_secret_free(speech_client) -> None:
    client, _ = speech_client
    token = _login(client)
    response = client.get(
        "/api/xunzhi/v1/speech/capabilities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["provider"] == "fake"
    assert payload["audioFormat"] == "pcm_s16le"
    assert payload["sampleRate"] == 16000
    assert "api_key" not in payload
    assert "api_secret" not in payload
    assert "secret_key" not in payload


def test_capabilities_without_authentication_are_rejected(speech_client) -> None:
    client, _ = speech_client
    response = client.get("/api/xunzhi/v1/speech/capabilities")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"
