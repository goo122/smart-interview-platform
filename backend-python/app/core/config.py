from functools import lru_cache
from secrets import token_urlsafe
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ai.capabilities import embedding_batch_limit


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
    ai_provider: Literal["unavailable", "fake", "openai_compatible"] = "unavailable"
    embedding_provider: Literal["unavailable", "fake", "openai_compatible"] = "unavailable"
    speech_to_text_provider: Literal["unavailable", "fake", "xunfei"] = "unavailable"
    ai_fake_mode: Literal["normal", "follow_up", "failure"] = "normal"
    ai_request_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    ai_max_retries: int = Field(default=2, ge=0, le=3)
    xunfei_asr_app_id: str | None = None
    xunfei_asr_api_key: str | None = None
    xunfei_asr_api_secret: str | None = None
    xunfei_asr_url: str = "wss://iat-api.xfyun.cn/v2/iat"
    asr_audio_format: Literal["pcm_s16le"] = "pcm_s16le"
    asr_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    asr_channels: int = Field(default=1, ge=1, le=1)
    asr_max_session_seconds: int = Field(default=120, ge=1, le=3600)
    asr_max_frame_bytes: int = Field(default=64 * 1024, ge=2, le=1024 * 1024)
    asr_max_audio_bytes: int = Field(default=5 * 1024 * 1024, ge=2, le=100 * 1024 * 1024)
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
    embedding_batch_size: int = Field(default=10, ge=1, le=512)
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
    report_primary_turn_weight: float = Field(default=1.0, ge=0.0)
    report_follow_up_turn_weight: float = Field(default=0.5, ge=0.0)
    report_technical_weight: float = Field(default=0.35, ge=0.0)
    report_relevance_weight: float = Field(default=0.20, ge=0.0)
    report_clarity_weight: float = Field(default=0.20, ge=0.0)
    report_depth_weight: float = Field(default=0.25, ge=0.0)
    report_aggregation_version: str = Field(default="v1", min_length=1, max_length=32)
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:local-development-only@localhost:5432/ai_interview"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        environment = self.app_env.strip().lower()
        if environment == "production" and (
            self.ai_provider == "fake"
            or self.embedding_provider == "fake"
            or self.speech_to_text_provider == "fake"
        ):
            raise ValueError("fake AI providers are not allowed in production")
        if self.speech_to_text_provider == "xunfei" and not all(
            self._has_value(value)
            for value in (
                self.xunfei_asr_app_id,
                self.xunfei_asr_api_key,
                self.xunfei_asr_api_secret,
            )
        ):
            raise ValueError(
                "xunfei speech provider requires app ID, API key and API secret"
            )
        if self.asr_max_frame_bytes > self.asr_max_audio_bytes:
            raise ValueError("asr_max_frame_bytes must not exceed asr_max_audio_bytes")
        if self.ai_provider == "openai_compatible" and not all(
            self._has_value(value)
            for value in (self.llm_api_key, self.llm_base_url, self.llm_model)
        ):
            raise ValueError(
                "openai_compatible AI provider requires API key, base URL and model"
            )
        if self.embedding_provider == "openai_compatible" and not all(
            self._has_value(value)
            for value in (
                self.embedding_api_key,
                self.embedding_base_url,
                self.embedding_model,
            )
        ):
            raise ValueError(
                "openai_compatible embedding provider requires API key, base URL and model"
            )
        provider_limit = embedding_batch_limit(
            self.embedding_provider, self.embedding_model
        )
        if provider_limit is not None and self.embedding_batch_size > provider_limit:
            raise ValueError(
                "embedding_batch_size must not exceed the configured provider limit "
                f"of {provider_limit}"
            )
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        if self.rag_top_k > self.rag_max_top_k:
            raise ValueError("rag_top_k must not exceed rag_max_top_k")
        if self.interview_min_answer_length > self.interview_max_answer_length:
            raise ValueError(
                "interview_min_answer_length must not exceed interview_max_answer_length"
            )
        dimension_total = (
            self.report_technical_weight
            + self.report_relevance_weight
            + self.report_clarity_weight
            + self.report_depth_weight
        )
        if abs(dimension_total - 1.0) > 1e-6:
            raise ValueError("report dimension weights must sum to 1")
        if self.report_primary_turn_weight == 0 and self.report_follow_up_turn_weight == 0:
            raise ValueError("at least one report turn weight must be positive")
        return self

    @staticmethod
    def _has_value(value: str | None) -> bool:
        return value is not None and bool(value.strip())


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
