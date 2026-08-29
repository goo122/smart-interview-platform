import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.ai.dependencies import get_ai_model_metadata
from app.ai.metadata import AiModelMetadataPort
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.chat.dependencies import get_chat_service
from app.modules.chat.schemas import (
    ChatRequest,
    ConversationResponse,
    CreateConversationRequest,
    CreateConversationResponse,
    EmptyResponse,
    MessageResponse,
    PageResponse,
)
from app.modules.chat.service import ChatEvent, ChatService

router = APIRouter(prefix="/xunzhi/v1/ai", tags=["chat"])


@router.post(
    "/conversations",
    response_model=CreateConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: CreateConversationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    model_metadata: Annotated[AiModelMetadataPort, Depends(get_ai_model_metadata)],
) -> CreateConversationResponse:
    conversation = await service.create_conversation(
        current_user.id,
        title=payload.title,
        first_message=payload.first_message,
        model_name=payload.model_name,
        ai_id=payload.ai_id,
    )
    return CreateConversationResponse(
        sessionId=str(conversation.id),
        conversationTitle=conversation.title,
        id=conversation.id,
        title=conversation.title,
    )


@router.get("/conversations", response_model=PageResponse[ConversationResponse])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    model_metadata: Annotated[AiModelMetadataPort, Depends(get_ai_model_metadata)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    ai_id: int | None = Query(default=None, alias="aiId"),
    conversation_status: int | None = Query(default=None, alias="status"),
    title: str | None = None,
) -> PageResponse[ConversationResponse]:
    conversations, total = await service.list_conversations(
        current_user.id, current, size, ai_id, conversation_status, title
    )
    records = [
        ConversationResponse.from_domain(
            item,
            username=current_user.username,
            model_metadata=model_metadata,
        )
        for item in conversations
    ]
    return PageResponse.build(records, total, current, size)


@router.get("/conversations/{session_id}", response_model=ConversationResponse)
async def get_conversation(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    model_metadata: Annotated[AiModelMetadataPort, Depends(get_ai_model_metadata)],
) -> ConversationResponse:
    conversation = await service.get_conversation(current_user.id, session_id)
    return ConversationResponse.from_domain(
        conversation,
        username=current_user.username,
        model_metadata=model_metadata,
    )


@router.post("/conversations/{session_id}/end", response_model=ConversationResponse)
@router.put("/conversations/{session_id}/end", response_model=ConversationResponse)
async def finish_conversation(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    model_metadata: Annotated[AiModelMetadataPort, Depends(get_ai_model_metadata)],
) -> ConversationResponse:
    conversation = await service.finish_conversation(current_user.id, session_id)
    return ConversationResponse.from_domain(
        conversation,
        username=current_user.username,
        model_metadata=model_metadata,
    )


@router.delete("/conversations/{session_id}", response_model=EmptyResponse)
async def delete_conversation(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> EmptyResponse:
    await service.delete_conversation(current_user.id, session_id)
    return EmptyResponse(message="Conversation deleted")


@router.get("/history/page", response_model=PageResponse[MessageResponse])
async def history_page(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    session_id: UUID = Query(alias="sessionId"),
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
) -> PageResponse[MessageResponse]:
    messages = await service.list_messages(current_user.id, session_id)
    total = len(messages)
    start = (current - 1) * size
    records = [MessageResponse.from_domain(message) for message in messages[start : start + size]]
    return PageResponse.build(records, total, current, size)


@router.get("/history/{session_id}", response_model=list[MessageResponse])
async def history(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> list[MessageResponse]:
    messages = await service.list_messages(current_user.id, session_id)
    return [MessageResponse.from_domain(message) for message in messages]


@router.get("/conversations/{session_id}/messages", response_model=list[MessageResponse])
async def conversation_messages(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> list[MessageResponse]:
    return await history(session_id, current_user, service)


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: UUID,
    payload: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    events = await service.stream_chat(
        current_user.id,
        session_id,
        payload.text,
        request_id=payload.request_id,
        knowledge_base_id=payload.knowledge_base_id,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )

    async def encode() -> AsyncIterator[str]:
        async for event in events:
            yield _encode_event(event)

    return StreamingResponse(
        encode(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _encode_event(event: ChatEvent) -> str:
    data = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.event}\ndata: {data}\n\n"
