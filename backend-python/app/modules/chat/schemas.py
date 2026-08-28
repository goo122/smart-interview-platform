from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.chat.domain import Conversation, Message, MessageCitation

T = TypeVar("T")


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    user_name: str | None = Field(default=None, alias="userName")
    first_message: str | None = Field(default=None, alias="firstMessage")
    ai_id: int | None = Field(default=None, alias="aiId")
    title: str | None = None
    model_name: str | None = Field(default=None, alias="modelName")


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    session_id: UUID | None = Field(default=None, alias="sessionId")
    input_message: str | None = Field(default=None, alias="inputMessage")
    content: str | None = None
    user_name: str | None = Field(default=None, alias="userName")
    ai_id: int | None = Field(default=None, alias="aiId")
    message_seq: int | None = Field(default=None, alias="messageSeq")
    request_id: str | None = Field(default=None, alias="requestId")
    image_urls: list[str] | None = Field(default=None, alias="imageUrls")
    media_list: list[object] | None = Field(default=None, alias="mediaList")
    file_urls: list[str] | None = Field(default=None, alias="fileUrls")
    knowledge_base_id: UUID | None = Field(default=None, alias="knowledgeBaseId")
    top_k: int | None = Field(default=None, alias="topK", ge=1, le=100)
    similarity_threshold: float | None = Field(
        default=None, alias="similarityThreshold", ge=0.0, le=1.0
    )

    @property
    def text(self) -> str:
        return self.input_message if self.input_message is not None else (self.content or "")


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID
    title: str
    status: int
    status_name: str = Field(alias="statusName")
    model_name: str | None = Field(default=None, alias="modelName")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    # Legacy fields consumed by the React application.
    session_id: str = Field(alias="sessionId")
    username: str | None = None
    ai_id: int | None = Field(default=None, alias="aiId")
    ai_name: str | None = Field(default=None, alias="aiName")
    message_count: int = Field(default=0, alias="messageCount")
    last_message_time: datetime | None = Field(default=None, alias="lastMessageTime")
    create_time: datetime = Field(alias="createTime")
    update_time: datetime = Field(alias="updateTime")

    @classmethod
    def from_domain(
        cls,
        conversation: Conversation,
        *,
        username: str | None = None,
        message_count: int = 0,
        ai_id: int | None = None,
    ) -> "ConversationResponse":
        numeric_status = 1 if conversation.status.value == "ACTIVE" else 2
        return cls(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            status=numeric_status,
            statusName=conversation.status.value,
            modelName=conversation.model_name,
            createdAt=conversation.created_at,
            updatedAt=conversation.updated_at,
            finishedAt=conversation.finished_at,
            sessionId=str(conversation.id),
            username=username,
            aiId=ai_id,
            messageCount=message_count,
            lastMessageTime=conversation.updated_at,
            createTime=conversation.created_at,
            updateTime=conversation.updated_at,
        )


class CreateConversationResponse(BaseModel):
    session_id: str = Field(alias="sessionId")
    conversation_title: str = Field(alias="conversationTitle")
    id: UUID
    title: str


class CitationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_id: str = Field(alias="sourceId")
    chunk_id: UUID = Field(alias="chunkId")
    document_id: UUID = Field(alias="documentId")
    document_name: str = Field(alias="documentName")
    page_number: int | None = Field(default=None, alias="pageNumber")
    score: float
    excerpt: str

    @classmethod
    def from_domain(cls, citation: MessageCitation) -> "CitationResponse":
        return cls(
            sourceId=citation.source_id,
            chunkId=citation.chunk_id,
            documentId=citation.document_id,
            documentName=citation.document_name,
            pageNumber=citation.page_number,
            score=citation.score,
            excerpt=citation.excerpt,
        )


class MessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    conversation_id: UUID = Field(alias="conversationId")
    role: str
    content: str
    status: str
    sequence: int
    request_id: str | None = Field(default=None, alias="requestId")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    # Legacy fields consumed by the React application.
    session_id: str = Field(alias="sessionId")
    message_type: int = Field(alias="messageType")
    message_content: str = Field(alias="messageContent")
    message_seq: int = Field(alias="messageSeq")
    response_time: int | None = Field(default=None, alias="responseTime")
    token_count: int | None = Field(default=None, alias="tokenCount")
    citations: list["CitationResponse"] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, message: Message) -> "MessageResponse":
        message_type = 1 if message.role.value == "USER" else 2
        return cls(
            id=message.id,
            conversationId=message.conversation_id,
            role=message.role.value,
            content=message.content,
            status=message.status.value,
            sequence=message.sequence,
            requestId=message.request_id,
            errorMessage=message.error_message,
            createdAt=message.created_at,
            completedAt=message.completed_at,
            sessionId=str(message.conversation_id),
            messageType=message_type,
            messageContent=message.content,
            messageSeq=message.sequence,
            citations=[CitationResponse.from_domain(citation) for citation in message.citations],
        )


class PageResponse[T](BaseModel):
    records: list[T]
    total: int
    size: int
    current: int
    pages: int

    @classmethod
    def build(cls, records: list[T], total: int, current: int, size: int) -> "PageResponse[T]":
        pages = (total + size - 1) // size if size else 0
        return cls(records=records, total=total, size=size, current=current, pages=pages)


class EmptyResponse(BaseModel):
    message: str
