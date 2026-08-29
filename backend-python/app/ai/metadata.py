"""Safe metadata for the single AI model configured at runtime.

This module intentionally exposes only display metadata. Provider credentials,
base URLs, prompts and other runtime configuration never cross this boundary.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings

RUNTIME_MODEL_ID = 1


@dataclass(frozen=True, slots=True)
class AiModelMetadata:
    """Public, non-sensitive metadata for one runtime model."""

    id: int | None
    ai_name: str
    ai_type: str
    model_name: str | None
    is_enabled: int
    enable_thinking: int


class AiModelMetadataPort(Protocol):
    """Synchronous metadata port used by API and chat services."""

    @property
    def current(self) -> AiModelMetadata: ...

    def list(
        self, current: int, size: int, is_enabled: int | None = None
    ) -> tuple[list[AiModelMetadata], int]: ...

    def resolve_selection(
        self, ai_id: int | None = None, model_name: str | None = None
    ) -> AiModelMetadata | None: ...

    def describe_conversation(self, model_name: str | None) -> AiModelMetadata: ...


class RuntimeAiModelMetadata:
    """Build model metadata directly from the validated runtime settings."""

    def __init__(self, settings: Settings) -> None:
        self._metadata = self._build(settings)

    @property
    def current(self) -> AiModelMetadata:
        return self._metadata

    def list(
        self, current: int, size: int, is_enabled: int | None = None
    ) -> tuple[list[AiModelMetadata], int]:
        records = (
            [self._metadata]
            if is_enabled is None or self._metadata.is_enabled == is_enabled
            else []
        )
        start = (max(current, 1) - 1) * max(size, 1)
        page_size = max(size, 1)
        return records[start : start + page_size], len(records)

    def resolve_selection(
        self, ai_id: int | None = None, model_name: str | None = None
    ) -> AiModelMetadata | None:
        metadata = self._metadata
        if metadata.is_enabled != 1:
            return None
        if ai_id is not None and ai_id != metadata.id:
            return None
        normalized_name = model_name.strip() if model_name else ""
        if normalized_name and (
            metadata.model_name is None
            or normalized_name.casefold() != metadata.model_name.casefold()
        ):
            return None
        return metadata

    def describe_conversation(self, model_name: str | None) -> AiModelMetadata:
        normalized_name = model_name.strip() if model_name else ""
        metadata = self._metadata
        if not normalized_name:
            return metadata
        if metadata.model_name and normalized_name.casefold() == metadata.model_name.casefold():
            return metadata
        return AiModelMetadata(
            id=None,
            ai_name=f"历史模型 {normalized_name}",
            ai_type="legacy",
            model_name=normalized_name,
            is_enabled=0,
            enable_thinking=0,
        )

    @classmethod
    def _build(cls, settings: Settings) -> AiModelMetadata:
        provider = settings.ai_provider
        if provider == "openai_compatible":
            model_name = (settings.llm_model or "").strip() or None
            return AiModelMetadata(
                id=RUNTIME_MODEL_ID,
                ai_name=_friendly_model_name(model_name),
                ai_type=provider,
                model_name=model_name,
                is_enabled=1,
                enable_thinking=0,
            )
        if provider == "fake":
            return AiModelMetadata(
                id=RUNTIME_MODEL_ID,
                ai_name="寻知开发测试模型",
                ai_type=provider,
                model_name="fake-interview-model",
                is_enabled=1,
                enable_thinking=0,
            )
        return AiModelMetadata(
            id=RUNTIME_MODEL_ID,
            ai_name="未配置 AI 模型",
            ai_type="unavailable",
            model_name=None,
            is_enabled=0,
            enable_thinking=0,
        )


def _friendly_model_name(model_name: str | None) -> str:
    if not model_name:
        return "兼容模型"
    normalized = model_name.casefold()
    if "qwen" in normalized:
        return f"通义千问 {model_name}"
    if "glm" in normalized:
        return f"智谱 {model_name}"
    return f"AI 模型 {model_name}"
