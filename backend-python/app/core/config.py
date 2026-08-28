from functools import lru_cache
from secrets import token_urlsafe

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
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
    rag_chunk_size: int = Field(default=800, ge=100, le=10000)
    rag_chunk_overlap: int = Field(default=120, ge=0, le=2000)
    rag_max_chunks_per_document: int = Field(default=1000, ge=1, le=10000)
    embedding_batch_size: int = Field(default=32, ge=1, le=512)
    embedding_dimensions: int = Field(default=1536, ge=1, le=4096)
    knowledge_max_file_size: int = Field(default=20 * 1024 * 1024, ge=1)
    knowledge_storage_dir: str = "./storage"
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:local-development-only@localhost:5432/ai_interview"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
