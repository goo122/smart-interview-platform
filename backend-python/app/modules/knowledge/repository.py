from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.domain import DocumentStatus, KnowledgeBase, KnowledgeDocument, utc_now
from app.modules.knowledge.exceptions import (
    DuplicateKnowledgeDocumentError,
    KnowledgeNameAlreadyExistsError,
)
from app.modules.knowledge.models import (
    KnowledgeBaseModel,
    KnowledgeDocumentModel,
)


class KnowledgeRepository(Protocol):
    async def create_base(self, base: KnowledgeBase) -> KnowledgeBase: ...

    async def get_base_for_user(self, base_id: UUID, user_id: UUID) -> KnowledgeBase | None: ...

    async def list_bases(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[KnowledgeBase], int]: ...

    async def delete_base_for_user(self, base_id: UUID, user_id: UUID) -> bool: ...

    async def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument: ...

    async def find_document_by_sha(
        self, base_id: UUID, sha256: str
    ) -> KnowledgeDocument | None: ...

    async def get_document_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> KnowledgeDocument | None: ...

    async def list_documents(
        self, base_id: UUID, current: int, size: int
    ) -> tuple[list[KnowledgeDocument], int]: ...

    async def mark_processing(self, document_id: UUID) -> KnowledgeDocument: ...

    async def claim_processing(
        self, document_id: UUID, stale_before: datetime, attempt: int = 1
    ) -> KnowledgeDocument | None: ...

    async def mark_ready(
        self, document_id: UUID, page_count: int, chunk_count: int
    ) -> KnowledgeDocument: ...

    async def mark_failed(
        self, document_id: UUID, error_code: str, error_message: str
    ) -> KnowledgeDocument: ...

    async def delete_document_for_user(self, document_id: UUID, user_id: UUID) -> bool: ...

    async def list_recoverable_documents(
        self, stale_before: datetime, limit: int = 100
    ) -> list[tuple[KnowledgeDocument, UUID]]: ...


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_base(self, base: KnowledgeBase) -> KnowledgeBase:
        row = KnowledgeBaseModel(
            id=base.id,
            user_id=base.user_id,
            name=base.name,
            description=base.description,
            created_at=base.created_at,
            updated_at=base.updated_at,
        )
        self._session.add(row)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise KnowledgeNameAlreadyExistsError("Knowledge base name already exists") from exc
        await self._session.refresh(row)
        return _base_to_domain(row)

    async def get_base_for_user(self, base_id: UUID, user_id: UUID) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBaseModel).where(
                KnowledgeBaseModel.id == base_id,
                KnowledgeBaseModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _base_to_domain(row) if row is not None else None

    async def list_bases(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[KnowledgeBase], int]:
        query = select(KnowledgeBaseModel).where(KnowledgeBaseModel.user_id == user_id)
        count = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        result = await self._session.execute(
            query.order_by(KnowledgeBaseModel.updated_at.desc())
            .offset((current - 1) * size)
            .limit(size)
        )
        return [_base_to_domain(row) for row in result.scalars().all()], int(count or 0)

    async def delete_base_for_user(self, base_id: UUID, user_id: UUID) -> bool:
        existing = await self.get_base_for_user(base_id, user_id)
        if existing is None:
            return False
        await self._session.execute(
            delete(KnowledgeBaseModel).where(KnowledgeBaseModel.id == base_id)
        )
        await self._session.commit()
        return True

    async def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        row = KnowledgeDocumentModel(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            original_filename=document.original_filename,
            safe_filename=document.safe_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            storage_path=document.storage_path,
            status=document.status.value,
            page_count=document.page_count,
            chunk_count=document.chunk_count,
            error_code=document.error_code,
            error_message=document.error_message,
            queued_at=document.queued_at,
            processing_started_at=document.processing_started_at,
            attempt_count=document.attempt_count,
            failure_code=document.failure_code,
            failure_message=document.failure_message,
            created_at=document.created_at,
            updated_at=document.updated_at,
            completed_at=document.completed_at,
        )
        self._session.add(row)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateKnowledgeDocumentError("This PDF is already imported") from exc
        await self._session.refresh(row)
        return _document_to_domain(row)

    async def find_document_by_sha(
        self, base_id: UUID, sha256: str
    ) -> KnowledgeDocument | None:
        result = await self._session.execute(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.knowledge_base_id == base_id,
                KnowledgeDocumentModel.sha256 == sha256,
            )
        )
        row = result.scalar_one_or_none()
        return _document_to_domain(row) if row is not None else None

    async def get_document_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> KnowledgeDocument | None:
        result = await self._session.execute(
            select(KnowledgeDocumentModel)
            .join(
                KnowledgeBaseModel,
                KnowledgeBaseModel.id == KnowledgeDocumentModel.knowledge_base_id,
            )
            .where(
                KnowledgeDocumentModel.id == document_id,
                KnowledgeBaseModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _document_to_domain(row) if row is not None else None

    async def list_documents(
        self, base_id: UUID, current: int, size: int
    ) -> tuple[list[KnowledgeDocument], int]:
        query = select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.knowledge_base_id == base_id
        )
        count = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        result = await self._session.execute(
            query.order_by(KnowledgeDocumentModel.updated_at.desc())
            .offset((current - 1) * size)
            .limit(size)
        )
        return [_document_to_domain(row) for row in result.scalars().all()], int(count or 0)

    async def mark_processing(self, document_id: UUID) -> KnowledgeDocument:
        started = utc_now()
        await self._session.execute(
            update(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .values(
                status=DocumentStatus.PROCESSING.value,
                processing_started_at=started,
                attempt_count=KnowledgeDocumentModel.attempt_count + 1,
                updated_at=started,
            )
        )
        await self._session.commit()
        return await self._get_document(document_id)

    async def claim_processing(
        self, document_id: UUID, stale_before: datetime, attempt: int = 1
    ) -> KnowledgeDocument | None:
        started = utc_now()
        result = await self._session.execute(
            update(KnowledgeDocumentModel)
            .where(
                KnowledgeDocumentModel.id == document_id,
                (
                    (KnowledgeDocumentModel.status == DocumentStatus.PENDING.value)
                    | (
                        (KnowledgeDocumentModel.status == DocumentStatus.PROCESSING.value)
                        & or_(
                            KnowledgeDocumentModel.processing_started_at.is_(None),
                            KnowledgeDocumentModel.processing_started_at < stale_before,
                        )
                    )
                    | (
                        (KnowledgeDocumentModel.status == DocumentStatus.PROCESSING.value)
                        & (KnowledgeDocumentModel.attempt_count == max(attempt - 1, 0))
                    )
                ),
            )
            .values(
                status=DocumentStatus.PROCESSING.value,
                processing_started_at=started,
                attempt_count=KnowledgeDocumentModel.attempt_count + 1,
                updated_at=started,
            )
        )
        await self._session.commit()
        if cast(CursorResult[Any], result).rowcount != 1:
            return None
        return await self._get_document(document_id)

    async def mark_ready(
        self, document_id: UUID, page_count: int, chunk_count: int
    ) -> KnowledgeDocument:
        completed = utc_now()
        await self._session.execute(
            update(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .values(
                status=DocumentStatus.READY.value,
                page_count=page_count,
                chunk_count=chunk_count,
                error_code=None,
                error_message=None,
                failure_code=None,
                failure_message=None,
                completed_at=completed,
                updated_at=completed,
            )
        )
        await self._session.commit()
        return await self._get_document(document_id)

    async def mark_failed(
        self, document_id: UUID, error_code: str, error_message: str
    ) -> KnowledgeDocument:
        failed_at = utc_now()
        await self._session.execute(
            update(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .values(
                status=DocumentStatus.FAILED.value,
                error_code=error_code,
                error_message=error_message,
                failure_code=error_code,
                failure_message=error_message,
                completed_at=None,
                updated_at=failed_at,
            )
        )
        await self._session.commit()
        return await self._get_document(document_id)

    async def delete_document_for_user(self, document_id: UUID, user_id: UUID) -> bool:
        existing = await self.get_document_for_user(document_id, user_id)
        if existing is None:
            return False
        await self._session.execute(
            delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == document_id)
        )
        await self._session.commit()
        return True

    async def list_recoverable_documents(
        self, stale_before: datetime, limit: int = 100
    ) -> list[tuple[KnowledgeDocument, UUID]]:
        result = await self._session.execute(
            select(KnowledgeDocumentModel, KnowledgeBaseModel.user_id)
            .join(
                KnowledgeBaseModel,
                KnowledgeBaseModel.id == KnowledgeDocumentModel.knowledge_base_id,
            )
            .where(
                or_(
                    KnowledgeDocumentModel.status == DocumentStatus.PENDING.value,
                    (
                        (KnowledgeDocumentModel.status == DocumentStatus.PROCESSING.value)
                        & (
                            KnowledgeDocumentModel.processing_started_at.is_(None)
                            | (KnowledgeDocumentModel.processing_started_at < stale_before)
                        )
                    ),
                )
            )
            .order_by(KnowledgeDocumentModel.updated_at.asc())
            .limit(limit)
        )
        return [
            (_document_to_domain(row), user_id)
            for row, user_id in result.all()
        ]

    async def _get_document(self, document_id: UUID) -> KnowledgeDocument:
        result = await self._session.execute(
            select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == document_id)
        )
        return _document_to_domain(result.scalar_one())


def _base_to_domain(row: KnowledgeBaseModel) -> KnowledgeBase:
    return KnowledgeBase(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _document_to_domain(row: KnowledgeDocumentModel) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=row.id,
        knowledge_base_id=row.knowledge_base_id,
        original_filename=row.original_filename,
        safe_filename=row.safe_filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        storage_path=row.storage_path,
        status=DocumentStatus(row.status),
        page_count=row.page_count,
        chunk_count=row.chunk_count,
        error_code=row.error_code,
        error_message=row.error_message,
        queued_at=row.queued_at,
        processing_started_at=row.processing_started_at,
        attempt_count=row.attempt_count,
        failure_code=row.failure_code or row.error_code,
        failure_message=row.failure_message or row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )
