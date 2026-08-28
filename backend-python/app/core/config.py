from functools import lru_cache
from secrets import token_urlsafe
from typing import Literal

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
    rag_top_k: int = Field(default=5, ge=1, le=100)
    rag_max_top_k: int = Field(default=20, ge=1, le=100)
    rag_similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    rag_max_context_tokens: int = Field(default=4000, ge=1, le=32000)
    rag_max_chunk_tokens: int = Field(default=1000, ge=1, le=8000)
    rag_no_result_policy: Literal["answer_without_context", "error"] = (
        "answer_without_context"
    )
    embedding_batch_size: int = Field(default=32, ge=1, le=512)
    embedding_dimensions: int = Field(default=1536, ge=1, le=4096)
    knowledge_max_file_size: int = Field(default=20 * 1024 * 1024, ge=1)
    knowledge_storage_dir: str = "./storage"
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    interview_max_follow_up_depth: int = Field(default=2, ge=0, le=10)
    interview_follow_up_score_threshold: int = Field(default=70, ge=0, le=100)
    interview_max_follow_ups_per_session: int = Field(default=5, ge=0, le=50)
    interview_min_answer_length: int = Field(default=10, ge=1, le=10000)
    interview_max_answer_length: int = Field(default=10000, ge=1, le=100000)
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:local-development-only@localhost:5432/ai_interview"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        if self.rag_top_k > self.rag_max_top_k:
            raise ValueError("rag_top_k must not exceed rag_max_top_k")
        if self.interview_min_answer_length > self.interview_max_answer_length:
            raise ValueError(
                "interview_min_answer_length must not exceed interview_max_answer_length"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
