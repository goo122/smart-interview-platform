from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class MessageCitation:
    id: UUID
    message_id: UUID
    chunk_id: UUID
    document_id: UUID
    source_id: str
    page_number: int | None
    score: float
    excerpt: str
    ordinal: int
    created_at: datetime
    document_name: str = ""


@dataclass(slots=True)
class Conversation:
    id: UUID
    user_id: UUID
    title: str
    status: ConversationStatus
    model_name: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    @classmethod
    def new(cls, user_id: UUID, title: str, model_name: str | None = None) -> "Conversation":
        now = utc_now()
        return cls(
            id=uuid4(),
            user_id=user_id,
            title=title,
            status=ConversationStatus.ACTIVE,
            model_name=model_name,
            created_at=now,
            updated_at=now,
            finished_at=None,
        )


@dataclass(slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    status: MessageStatus
    sequence: int
    request_id: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    citations: list[MessageCitation] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        sequence: int,
        request_id: str | None = None,
        status: MessageStatus = MessageStatus.COMPLETED,
    ) -> "Message":
        now = utc_now()
        return cls(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            sequence=sequence,
            request_id=request_id,
            error_message=None,
            created_at=now,
            completed_at=now if status == MessageStatus.COMPLETED else None,
        )
