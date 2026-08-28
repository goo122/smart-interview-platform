from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class KnowledgeBase:
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(cls, user_id: UUID, name: str, description: str | None = None) -> "KnowledgeBase":
        now = utc_now()
        return cls(uuid4(), user_id, name, description, now, now)


@dataclass(slots=True)
class KnowledgeDocument:
    id: UUID
    knowledge_base_id: UUID
    original_filename: str
    safe_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_path: str
    status: DocumentStatus
    page_count: int
    chunk_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @classmethod
    def new(
        cls,
        knowledge_base_id: UUID,
        original_filename: str,
        safe_filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        storage_path: str,
    ) -> "KnowledgeDocument":
        now = utc_now()
        return cls(
            id=uuid4(),
            knowledge_base_id=knowledge_base_id,
            original_filename=original_filename,
            safe_filename=safe_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            storage_path=storage_path,
            status=DocumentStatus.PENDING,
            page_count=0,
            chunk_count=0,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )


@dataclass(frozen=True, slots=True)
class PdfPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_index: int
    page_number: int | None
    content: str
    token_count: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class StoredChunk:
    chunk_index: int
    page_number: int | None
    content: str
    token_count: int
    content_hash: str
    embedding: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk returned by a scoped vector search."""

    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int | None
    content: str
    score: float
