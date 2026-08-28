from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat import ChatModelPort
from app.modules.auth.dependencies import get_db_session
from app.modules.chat.repository import (
    ConversationRepository,
    MessageRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.modules.chat.service import ChatService


async def get_conversation_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationRepository:
    return SqlAlchemyConversationRepository(session)


async def get_message_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageRepository:
    return SqlAlchemyMessageRepository(session)


def get_chat_model(request: Request) -> ChatModelPort:
    return cast(ChatModelPort, request.app.state.chat_model)


def get_chat_service(
    conversation_repository: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
    chat_model: Annotated[ChatModelPort, Depends(get_chat_model)],
) -> ChatService:
    return ChatService(conversation_repository, message_repository, chat_model)
