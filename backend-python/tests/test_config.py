import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_values() -> dict[str, object]:
    return {
        "_env_file": None,
        "app_env": "production",
        "secret_key": "production-signing-key-with-at-least-32-characters",
        "database_url": "postgresql+asyncpg://app:strong-password@postgres:5432/interview",
        "redis_url": "redis://redis:6379/0",
        "ai_provider": "openai_compatible",
        "llm_api_key": "provider-key",
        "llm_base_url": "https://llm.invalid/v1",
        "llm_model": "chat-model",
        "embedding_provider": "openai_compatible",
        "embedding_api_key": "embedding-key",
        "embedding_base_url": "https://embedding.invalid/v1",
        "embedding_model": "embedding-model",
    }


def _production_settings(**overrides: object) -> Settings:
    values = _production_values()
    values.update(overrides)
    return Settings(**values)


def test_complete_production_configuration_is_accepted() -> None:
    settings = _production_settings()

    assert settings.app_env == "production"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"debug": True}, "debug mode"),
        ({"ai_provider": "unavailable"}, "requires an openai_compatible AI"),
        ({"embedding_provider": "unavailable"}, "requires an openai_compatible embedding"),
        ({"secret_key": "replace-me"}, "at least 32 non-placeholder"),
        (
            {"database_url": "postgresql+asyncpg://app:password@localhost:5432/interview"},
            "database must not use a loopback host",
        ),
        ({"redis_url": "redis://127.0.0.1:6379/0"}, "Redis must not use a loopback host"),
    ],
)
def test_unsafe_production_configuration_is_rejected(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _production_settings(**overrides)


def test_production_secret_must_be_explicit() -> None:
    values = _production_values()
    del values["secret_key"]
    with pytest.raises(ValidationError, match="APP_SECRET_KEY to be explicitly configured"):
        Settings(**values)


def test_app_env_uses_documented_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")

    assert Settings(_env_file=None).app_env == "test"
