import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from app.ai.embedding import EmbeddingPort
from app.core.config import Settings
from app.infrastructure.storage.files import FileStoragePort
from app.infrastructure.storage.pdf import PdfParserPort
from app.infrastructure.vectorstore.port import VectorStorePort
from app.modules.knowledge.domain import (
    KnowledgeBase,
    KnowledgeDocument,
    StoredChunk,
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
    UnsupportedPdfError,
)
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.splitter import TextSplitterPort
from app.workers.queue import TaskQueuePort


class KnowledgeService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        file_storage: FileStoragePort,
        pdf_parser: PdfParserPort,
        text_splitter: TextSplitterPort,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort,
        task_queue: TaskQueuePort,
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

    async def upload_document(
        self,
        user_id: UUID,
        base_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
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

        await self._task_queue.enqueue(lambda: self._process_document(document))
        return await self.get_document(user_id, document.id)

    async def delete_document(self, user_id: UUID, document_id: UUID) -> None:
        document = await self.get_document(user_id, document_id)
        await self._vector_store.delete_document(document.id)
        await self._file_storage.delete(document.storage_path)
        if not await self._repository.delete_document_for_user(document.id, user_id):
            raise KnowledgeDocumentNotFoundError("Knowledge document not found")

    async def _process_document(self, document: KnowledgeDocument) -> None:
        await self._repository.mark_processing(document.id)
        try:
            pages = await self._pdf_parser.parse(document.storage_path)
            chunks = list(self._text_splitter.split(pages))
            if not chunks:
                raise UnsupportedPdfError("PDF contains no extractable text")
            if len(chunks) > self._settings.rag_max_chunks_per_document:
                raise ChunkLimitExceededError("PDF contains too many text chunks")
            stored_chunks = await self._embed_chunks(chunks)
            await self._vector_store.store_chunks(document.id, stored_chunks)
            await self._repository.mark_ready(document.id, len(pages), len(stored_chunks))
        except (InvalidPdfError, UnsupportedPdfError, KnowledgeImportError) as exc:
            await self._fail_document(document, exc.code, exc.message)
        except Exception:
            await self._fail_document(
                document,
                "EMBEDDING_FAILED",
                "Document import failed",
            )

    async def _embed_chunks(self, chunks: Sequence[Any]) -> list[StoredChunk]:
        result: list[StoredChunk] = []
        batch_size = self._settings.embedding_batch_size
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = await self._embedding.embed_documents([chunk.content for chunk in batch])
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
        return result

    async def _fail_document(
        self, document: KnowledgeDocument, error_code: str, message: str
    ) -> None:
        await self._vector_store.rollback()
        await self._vector_store.delete_document(document.id)
        await self._repository.mark_failed(document.id, error_code, message)
        await self._file_storage.delete(document.storage_path)
