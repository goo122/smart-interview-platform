from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat import ChatModelPort
from app.ai.embedding import EmbeddingPort
from app.core.config import Settings, get_settings
from app.infrastructure.vectorstore.retriever import PgVectorRetriever
from app.modules.auth.dependencies import get_db_session
from app.modules.chat.context import ContextProvider, RagContextProvider
from app.modules.chat.repository import (
    ConversationRepository,
    MessageRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.modules.chat.service import ChatService
from app.modules.knowledge.context import ContextAssembler
from app.modules.knowledge.dependencies import get_embedding, get_knowledge_repository
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.retrieval import RetrieverPort


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


async def get_retriever(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrieverPort:
    return PgVectorRetriever(session, settings.embedding_dimensions)


def get_context_provider(
    repository: Annotated[KnowledgeRepository, Depends(get_knowledge_repository)],
    embedding: Annotated[EmbeddingPort, Depends(get_embedding)],
    retriever: Annotated[RetrieverPort, Depends(get_retriever)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContextProvider:
    return RagContextProvider(
        repository,
        embedding,
        retriever,
        ContextAssembler(settings.rag_max_context_tokens, settings.rag_max_chunk_tokens),
        settings,
    )


def get_chat_service(
    conversation_repository: Annotated[
        ConversationRepository, Depends(get_conversation_repository)
    ],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
    chat_model: Annotated[ChatModelPort, Depends(get_chat_model)],
    context_provider: Annotated[ContextProvider, Depends(get_context_provider)],
) -> ChatService:
    return ChatService(
        conversation_repository, message_repository, chat_model, context_provider
    )
