from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.ai.dependencies import get_ai_model_metadata
from app.ai.metadata import AiModelMetadata, AiModelMetadataPort
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User

router = APIRouter(prefix="/xunzhi/v1", tags=["ai"])


class AiPropertyResponse(BaseModel):
    """Safe model metadata exposed to the frontend model selector."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    ai_name: str = Field(alias="aiName")
    ai_type: str = Field(alias="aiType")
    model_name: str | None = Field(default=None, alias="modelName")
    is_enabled: int = Field(alias="isEnabled")
    enable_thinking: int = Field(alias="enableThinking")

    @classmethod
    def from_metadata(cls, metadata: AiModelMetadata) -> "AiPropertyResponse":
        if metadata.id is None:
            raise ValueError("A listed model must have a stable id")
        return cls(
            id=metadata.id,
            aiName=metadata.ai_name,
            aiType=metadata.ai_type,
            modelName=metadata.model_name,
            isEnabled=metadata.is_enabled,
            enableThinking=metadata.enable_thinking,
        )


T = TypeVar("T")


class AiPropertiesPageResponse[T](BaseModel):
    records: list[T]
    total: int
    size: int
    current: int
    pages: int

    @classmethod
    def build(
        cls, records: list[T], total: int, current: int, size: int
    ) -> "AiPropertiesPageResponse[T]":
        return cls(
            records=records,
            total=total,
            size=size,
            current=current,
            pages=(total + size - 1) // size if size else 0,
        )


@router.get(
    "/ai-properties",
    response_model=AiPropertiesPageResponse[AiPropertyResponse],
)
async def list_ai_properties(
    _current_user: Annotated[User, Depends(get_current_user)],
    model_metadata: Annotated[AiModelMetadataPort, Depends(get_ai_model_metadata)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=100),
    is_enabled: int | None = Query(default=None, alias="isEnabled", ge=0, le=1),
) -> AiPropertiesPageResponse[AiPropertyResponse]:
    records, total = model_metadata.list(current, size, is_enabled)
    return AiPropertiesPageResponse.build(
        [AiPropertyResponse.from_metadata(item) for item in records],
        total,
        current,
        size,
    )
