from typing import Annotated, cast

from fastapi import Depends, Request

from app.ai.metadata import AiModelMetadataPort, RuntimeAiModelMetadata
from app.core.config import Settings, get_settings


def get_ai_model_metadata(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AiModelMetadataPort:
    """Return the metadata object built with the application runtime settings."""

    metadata = getattr(request.app.state, "ai_model_metadata", None)
    if metadata is not None:
        return cast(AiModelMetadataPort, metadata)
    return RuntimeAiModelMetadata(settings)
