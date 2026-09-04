import hashlib
import logging
import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from app.ai.embedding import EmbeddingPort
from app.core.config import Settings
from app.infrastructure.storage.files import FileStoragePort
from app.infrastructure.storage.pdf import PdfParserPort
from app.infrastructure.vectorstore.port import VectorStorePort
from app.modules.knowledge.domain import (
    DocumentStatus,
    KnowledgeBase,
    KnowledgeDocument,
    StoredChunk,
    utc_now,
)
from app.modules.knowledge.exceptions import (
    ChunkLimitExceededError,
    DuplicateKnowledgeDocumentError,
    EmbeddingDimensionError,
    InvalidKnowledgeBaseError,
    InvalidPdfError,
    KnowledgeBaseNotFoundError,
    KnowledgeDocumentNotFoundError,
    KnowledgeImportError,
    KnowledgeQueueUnavailableError,
    RetryableKnowledgeImportError,
    UnsupportedPdfError,
)
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.splitter import TextSplitterPort
from app.workers.queue import DocumentImportJob, DocumentTaskQueuePort

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        file_storage: FileStoragePort,
        pdf_parser: PdfParserPort,
        text_splitter: TextSplitterPort,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort,
        task_queue: DocumentTaskQueuePort,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._file_storage = file_storage
        self._pdf_parser = pdf_parser
        self._text_splitter = text_splitter
        self._embedding = embedding
        self._vector_store = vector_store
        self._task_queue = task_queue
        self._settings = settings
        task_queue.bind_inline_handler(self.process_document_job)

    async def create_base(
        self, user_id: UUID, name: str, description: str | None = None
    ) -> KnowledgeBase:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 200:
            raise InvalidKnowledgeBaseError("Knowledge base name is invalid")
        return await self._repository.create_base(
            KnowledgeBase.new(user_id, clean_name, description.strip() if description else None)
        )

    async def list_bases(
        self, user_id: UUID, current: int = 1, size: int = 10
    ) -> tuple[list[KnowledgeBase], int]:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        return await self._repository.list_bases(user_id, current, size)

    async def get_base(self, user_id: UUID, base_id: UUID) -> KnowledgeBase:
        base = await self._repository.get_base_for_user(base_id, user_id)
        if base is None:
            raise KnowledgeBaseNotFoundError("Knowledge base not found")
        return base

    async def delete_base(self, user_id: UUID, base_id: UUID) -> None:
        await self.get_base(user_id, base_id)
        documents, _ = await self._repository.list_documents(base_id, 1, 10000)
        for document in documents:
            await self._vector_store.delete_document(document.id)
            await self._file_storage.delete(document.storage_path)
        if not await self._repository.delete_base_for_user(base_id, user_id):
            raise KnowledgeBaseNotFoundError("Knowledge base not found")

    async def list_documents(
        self, user_id: UUID, base_id: UUID, current: int = 1, size: int = 10
    ) -> tuple[list[KnowledgeDocument], int]:
        await self.get_base(user_id, base_id)
        current = max(current, 1)
        size = min(max(size, 1), 100)
        return await self._repository.list_documents(base_id, current, size)

    async def get_document(self, user_id: UUID, document_id: UUID) -> KnowledgeDocument:
        document = await self._repository.get_document_for_user(document_id, user_id)
        if document is None:
            raise KnowledgeDocumentNotFoundError("Knowledge document not found")
        return document

    async def get_latest_ready_document(
        self, user_id: UUID, base_id: UUID
    ) -> KnowledgeDocument:
        await self.get_base(user_id, base_id)
        documents, _ = await self._repository.list_documents(base_id, 1, 10000)
        for document in documents:
            if document.status == DocumentStatus.READY:
                return document
        raise KnowledgeDocumentNotFoundError("Ready resume document not found")

    async def read_document_content(self, user_id: UUID, document_id: UUID) -> bytes:
        document = await self.get_document(user_id, document_id)
        try:
            return await self._file_storage.read(document.storage_path)
        except FileNotFoundError as exc:
            raise KnowledgeDocumentNotFoundError("Knowledge document file not found") from exc

    async def upload_document(
        self,
        user_id: UUID,
        base_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
        request_id: str = "",
    ) -> KnowledgeDocument:
        await self.get_base(user_id, base_id)
        # Normalize both POSIX and Windows separators before retaining the display name.
        normalized_name = Path((filename or "document.pdf").replace("\\", "/")).name
        if Path(normalized_name).suffix.lower() != ".pdf":
            raise InvalidPdfError("Only PDF files are supported")
        if content_type.strip().lower() != "application/pdf":
            raise InvalidPdfError("Only PDF files are supported")
        if len(content) > self._settings.knowledge_max_file_size:
            raise InvalidPdfError("PDF file exceeds the maximum size")
        if not content.startswith(b"%PDF-"):
            raise InvalidPdfError("Invalid PDF file")

        digest = hashlib.sha256(content).hexdigest()
        if await self._repository.find_document_by_sha(base_id, digest) is not None:
            raise DuplicateKnowledgeDocumentError("This PDF is already imported")

        stored = await self._file_storage.save_pdf(content)
        document = KnowledgeDocument.new(
            knowledge_base_id=base_id,
            original_filename=normalized_name[:255],
            safe_filename=stored.safe_filename,
            content_type="application/pdf",
            size_bytes=len(content),
            sha256=digest,
            storage_path=stored.path,
        )
        try:
            await self._repository.create_document(document)
        except Exception:
            await self._file_storage.delete(stored.path)
            raise
        pending_snapshot = replace(document)

        try:
            await self._task_queue.enqueue_document(
                DocumentImportJob(
                    document_id=document.id,
                    user_id=user_id,
                    knowledge_base_id=base_id,
                    request_id=request_id,
                )
            )
        except Exception as exc:
            await self._repository.mark_failed(
                document.id,
                "QUEUE_UNAVAILABLE",
                "Document processing could not be scheduled",
            )
            await self._file_storage.delete(document.storage_path)
            raise KnowledgeQueueUnavailableError(
                "Document processing is temporarily unavailable"
            ) from exc
        # The queue contract is asynchronous: the API must return the durable
        # PENDING snapshot instead of waiting for the worker to update it.
        return pending_snapshot

    async def delete_document(self, user_id: UUID, document_id: UUID) -> None:
        document = await self.get_document(user_id, document_id)
        await self._vector_store.delete_document(document.id)
        await self._file_storage.delete(document.storage_path)
        if not await self._repository.delete_document_for_user(document.id, user_id):
            raise KnowledgeDocumentNotFoundError("Knowledge document not found")

    async def process_document_job(self, job: DocumentImportJob, attempt: int = 1) -> None:
        document = await self._repository.get_document_for_user(job.document_id, job.user_id)
        if document is None or document.knowledge_base_id != job.knowledge_base_id:
            return
        stale_before = utc_now() - timedelta(
            seconds=self._settings.knowledge_processing_stale_seconds
        )
        claimed = await self._repository.claim_processing(document.id, stale_before, attempt)
        if claimed is None:
            return
        document = claimed
        started_at = time.perf_counter()
        common_log = {
            "document_id": str(document.id),
            "knowledge_base_id": str(document.knowledge_base_id),
            "request_id": job.request_id,
            "attempt": attempt,
            "provider": self._settings.embedding_provider,
        }
        logger.info("Knowledge document processing started", extra=common_log)
        try:
            # A stale recovery or redelivered job must not append duplicate chunks.
            await self._vector_store.delete_document(document.id)
            parse_started_at = time.perf_counter()
            pages = await self._pdf_parser.parse(document.storage_path)
            pdf_parse_ms = round((time.perf_counter() - parse_started_at) * 1000, 2)
            split_started_at = time.perf_counter()
            chunks = list(self._text_splitter.split(pages))
            text_split_ms = round((time.perf_counter() - split_started_at) * 1000, 2)
            if not chunks:
                raise UnsupportedPdfError("PDF contains no extractable text")
            if len(chunks) > self._settings.rag_max_chunks_per_document:
                raise ChunkLimitExceededError("PDF contains too many text chunks")
            embedding_started_at = time.perf_counter()
            stored_chunks = await self._embed_chunks(chunks)
            embedding_ms = round((time.perf_counter() - embedding_started_at) * 1000, 2)
            vector_storage_started_at = time.perf_counter()
            await self._vector_store.store_chunks(document.id, stored_chunks)
            vector_storage_ms = round(
                (time.perf_counter() - vector_storage_started_at) * 1000, 2
            )
            status_storage_started_at = time.perf_counter()
            await self._repository.mark_ready(document.id, len(pages), len(stored_chunks))
            status_storage_ms = round(
                (time.perf_counter() - status_storage_started_at) * 1000, 2
            )
            logger.info(
                "Knowledge document processing completed",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "pdf_parse_ms": pdf_parse_ms,
                    "text_split_ms": text_split_ms,
                    "embedding_ms": embedding_ms,
                    "vector_storage_ms": vector_storage_ms,
                    "status_storage_ms": status_storage_ms,
                    "page_count": len(pages),
                    "chunk_count": len(stored_chunks),
                },
            )
        except (InvalidPdfError, UnsupportedPdfError, KnowledgeImportError) as exc:
            await self._fail_document(document, exc.code, exc.message)
            logger.warning(
                "Knowledge document processing failed permanently",
                extra={
                    **common_log,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "failure_code": exc.code,
                },
            )
        except Exception as exc:
            if attempt < self._settings.knowledge_task_max_attempts:
                await self._vector_store.rollback()
                await self._vector_store.delete_document(document.id)
                logger.warning(
                    "Knowledge document processing will retry",
                    extra={
                        **common_log,
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                        "failure_category": type(exc).__name__,
                    },
                )
                raise RetryableKnowledgeImportError("Document processing will be retried") from exc
            await self._fail_document(
                document,
                "RETRY_EXHAUSTED",
                "Document processing failed after several attempts",
            )

    async def _embed_chunks(self, chunks: Sequence[Any]) -> list[StoredChunk]:
        result: list[StoredChunk] = []
        configured_batch_size = self._settings.embedding_batch_size
        provider_limit = self._embedding.max_batch_size
        batch_size = (
            min(configured_batch_size, provider_limit)
            if provider_limit is not None
            else configured_batch_size
        )
        batch_count = (len(chunks) + batch_size - 1) // batch_size if chunks else 0
        started_at = time.perf_counter()
        common_log = {
            "provider": self._settings.embedding_provider,
            "model": self._settings.embedding_model,
            "input_count": len(chunks),
            "configured_batch_size": configured_batch_size,
            "effective_batch_size": batch_size,
            "batch_count": batch_count,
        }
        logger.info("Embedding document chunks", extra=common_log)
        try:
            for start in range(0, len(chunks), batch_size):
                batch_number = (start // batch_size) + 1
                batch = chunks[start : start + batch_size]
                logger.info(
                    "Embedding document batch",
                    extra={**common_log, "batch_number": batch_number},
                )
                vectors = await self._embedding.embed_documents(
                    [chunk.content for chunk in batch]
                )
                if len(vectors) != len(batch):
                    raise EmbeddingDimensionError("Embedding result count is invalid")
                for chunk, vector in zip(batch, vectors, strict=True):
                    if len(vector) != self._embedding.dimensions:
                        raise EmbeddingDimensionError("Embedding dimensions are invalid")
                    if len(vector) != self._settings.embedding_dimensions:
                        raise EmbeddingDimensionError("Embedding dimensions are invalid")
                    result.append(
                        StoredChunk(
                            chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number,
                            content=chunk.content,
                            token_count=chunk.token_count,
                            content_hash=chunk.content_hash,
                            embedding=tuple(float(value) for value in vector),
                        )
                    )
        except Exception as exc:
            logger.warning(
                "Embedding document failed",
                extra={
                    **common_log,
                    "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "failure_category": type(exc).__name__,
                    "success": False,
                },
            )
            raise
        logger.info(
            "Embedding document completed",
            extra={
                **common_log,
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "success": True,
            },
        )
        return result

    async def _fail_document(
        self, document: KnowledgeDocument, error_code: str, message: str
    ) -> None:
        await self._vector_store.rollback()
        await self._vector_store.delete_document(document.id)
        await self._repository.mark_failed(document.id, error_code, message)
