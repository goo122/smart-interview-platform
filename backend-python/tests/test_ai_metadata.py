from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.ai.dependencies import get_ai_model_metadata
from app.ai.metadata import RUNTIME_MODEL_ID, RuntimeAiModelMetadata
from app.core.config import Settings
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User


def _user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username="metadata-user",
        email="metadata@example.com",
        password_hash="not-returned",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@contextmanager
def _client(metadata: RuntimeAiModelMetadata) -> Iterator[TestClient]:
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_ai_model_metadata] = lambda: metadata
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_openai_metadata_is_safe_and_uses_runtime_model() -> None:
    secret = "test-api-key-not-returned"
    base_url = "https://dashscope.example.invalid/compatible-mode/v1"
    metadata = RuntimeAiModelMetadata(
        Settings(
            _env_file=None,
            ai_provider="openai_compatible",
            embedding_provider="unavailable",
            llm_api_key=secret,
            llm_base_url=base_url,
            llm_model="qwen-plus",
        )
    )

    with _client(metadata) as client:
        response = client.get(
            "/api/xunzhi/v1/ai-properties",
            params={"isEnabled": 1, "current": 1, "size": 100},
        )

    assert response.status_code == 200
    assert response.json() == {
        "records": [
            {
                "id": RUNTIME_MODEL_ID,
                "aiName": "通义千问 qwen-plus",
                "aiType": "openai_compatible",
                "modelName": "qwen-plus",
                "isEnabled": 1,
                "enableThinking": 0,
            }
        ],
        "total": 1,
        "size": 100,
        "current": 1,
        "pages": 1,
    }
    body = response.text
    assert secret not in body
    assert base_url not in body
    assert "apiKey" not in body
    assert "apiSecret" not in body
    assert "systemPrompt" not in body


def test_fake_and_unavailable_provider_filters() -> None:
    fake = RuntimeAiModelMetadata(
        Settings(_env_file=None, app_env="test", ai_provider="fake")
    )
    unavailable = RuntimeAiModelMetadata(Settings(_env_file=None))

    with _client(fake) as client:
        enabled_fake = client.get("/api/xunzhi/v1/ai-properties?isEnabled=1")
        disabled_fake = client.get("/api/xunzhi/v1/ai-properties?isEnabled=0")
    with _client(unavailable) as client:
        enabled_unavailable = client.get("/api/xunzhi/v1/ai-properties?isEnabled=1")
        disabled_unavailable = client.get("/api/xunzhi/v1/ai-properties?isEnabled=0")

    assert enabled_fake.json()["records"][0] == {
        "id": RUNTIME_MODEL_ID,
        "aiName": "寻知开发测试模型",
        "aiType": "fake",
        "modelName": "fake-interview-model",
        "isEnabled": 1,
        "enableThinking": 0,
    }
    assert disabled_fake.json()["records"] == []
    assert enabled_unavailable.json()["records"] == []
    assert disabled_unavailable.json()["records"][0]["isEnabled"] == 0
    assert disabled_unavailable.json()["records"][0]["aiName"] == "未配置 AI 模型"


def test_ai_properties_auth_pagination_and_validation() -> None:
    metadata = RuntimeAiModelMetadata(
        Settings(_env_file=None, app_env="test", ai_provider="fake")
    )
    app.dependency_overrides[get_ai_model_metadata] = lambda: metadata
    try:
        with TestClient(app) as client:
            unauthorized = client.get("/api/xunzhi/v1/ai-properties")
            assert unauthorized.status_code == 401

            app.dependency_overrides[get_current_user] = _user
            response = client.get(
                "/api/xunzhi/v1/ai-properties",
                params={"current": 1, "size": 1, "isEnabled": 1},
            )
            assert response.status_code == 200
            assert response.json()["total"] == 1
            assert response.json()["pages"] == 1
            assert response.json()["current"] == 1
            assert response.json()["size"] == 1
            assert client.get(
                "/api/xunzhi/v1/ai-properties", params={"current": 0}
            ).status_code == 422
            assert client.get(
                "/api/xunzhi/v1/ai-properties", params={"size": 101}
            ).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_runtime_model_id_is_stable() -> None:
    first = RuntimeAiModelMetadata(
        Settings(
            _env_file=None,
            ai_provider="openai_compatible",
            llm_api_key="key-a",
            llm_base_url="https://one.example.invalid/v1",
            llm_model="qwen-plus",
        )
    )
    second = RuntimeAiModelMetadata(
        Settings(
            _env_file=None,
            ai_provider="openai_compatible",
            llm_api_key="key-b",
            llm_base_url="https://two.example.invalid/v1",
            llm_model="qwen-plus",
        )
    )

    assert first.current.id == second.current.id == RUNTIME_MODEL_ID
