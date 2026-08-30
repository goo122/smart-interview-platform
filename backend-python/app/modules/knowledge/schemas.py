from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.knowledge.domain import KnowledgeBase, KnowledgeDocument

T = TypeVar("T")


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, base: KnowledgeBase) -> "KnowledgeBaseResponse":
        return cls.model_validate(base)


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    original_filename: str
    safe_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: str
    page_count: int
    chunk_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    queued_at: datetime | None
    processing_started_at: datetime | None
    attempt_count: int
    failure_code: str | None
    failure_message: str | None

    @classmethod
    def from_domain(cls, document: KnowledgeDocument) -> "KnowledgeDocumentResponse":
        # storage_path is intentionally not part of the public response.
        return cls(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            original_filename=document.original_filename,
            safe_filename=document.safe_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            status=document.status.value,
            page_count=document.page_count,
            chunk_count=document.chunk_count,
            error_code=document.error_code,
            error_message=document.error_message,
            created_at=document.created_at,
            updated_at=document.updated_at,
            completed_at=document.completed_at,
            queued_at=document.queued_at,
            processing_started_at=document.processing_started_at,
            attempt_count=document.attempt_count,
            failure_code=document.failure_code,
            failure_message=document.failure_message,
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


class DeleteResponse(BaseModel):
    message: str = Field(default="Deleted")
