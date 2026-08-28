from functools import lru_cache
from secrets import token_urlsafe

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
    )

    app_env: str = "development"
    debug: bool = False
    secret_key: str = Field(default_factory=lambda: token_urlsafe(32))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:local-development-only@localhost:5432/ai_interview"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
