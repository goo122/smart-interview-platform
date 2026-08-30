import asyncio
from collections.abc import Iterator, Sequence
from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.ai.embedding import FakeEmbedding
from app.core.config import Settings, get_settings
from app.core.exceptions import UserAlreadyExistsError
from app.infrastructure.storage.files import FakeFileStorage
from app.infrastructure.storage.pdf import FakePdfParser
from app.main import app
from app.modules.auth.dependencies import get_session_store, get_user_repository
from app.modules.auth.domain import User
from app.modules.knowledge.dependencies import (
    get_document_task_queue,
    get_embedding,
    get_file_storage,
    get_knowledge_repository,
    get_pdf_parser,
    get_text_splitter,
    get_vector_store,
)
from app.modules.knowledge.domain import (
    DocumentStatus,
    KnowledgeBase,
    KnowledgeDocument,
    PdfPage,
    StoredChunk,
    TextChunk,
    utc_now,
)
from app.modules.knowledge.exceptions import (
    DuplicateKnowledgeDocumentError,
    EmbeddingDimensionError,
    KnowledgeNameAlreadyExistsError,
    KnowledgeQueueUnavailableError,
)
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter
from app.workers.queue import (
    DocumentImportHandler,
    DocumentImportJob,
    InlineDocumentTaskQueue,
)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: list[User] = []

    async def create(self, user: User) -> User:
        if await self.get_by_username(user.username) or await self.get_by_email(user.email):
            raise UserAlreadyExistsError("Username or email already exists")
        self.users.append(user)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next((item for item in self.users if item.id == user_id), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((item for item in self.users if item.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return next((item for item in self.users if item.email == email), None)


class FakeSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[UUID, UUID] = {}

    async def save_refresh_session(self, jti: UUID, user_id: UUID, ttl_seconds: int) -> None:
        self.sessions[jti] = user_id

    async def consume_refresh_session(self, jti: UUID) -> UUID | None:
        return self.sessions.pop(jti, None)

    async def revoke_refresh_session(self, jti: UUID, ttl_seconds: int) -> None:
        self.sessions.pop(jti, None)


class FakeKnowledgeRepository:
    def __init__(self) -> None:
        self.bases: dict[UUID, KnowledgeBase] = {}
        self.documents: dict[UUID, KnowledgeDocument] = {}

    async def create_base(self, base: KnowledgeBase) -> KnowledgeBase:
        if any(
            item.user_id == base.user_id and item.name == base.name
            for item in self.bases.values()
        ):
            raise KnowledgeNameAlreadyExistsError("Knowledge base name already exists")
        self.bases[base.id] = base
        return base

    async def get_base_for_user(self, base_id: UUID, user_id: UUID) -> KnowledgeBase | None:
        item = self.bases.get(base_id)
        return item if item and item.user_id == user_id else None

    async def list_bases(
        self, user_id: UUID, current: int, size: int
    ) -> tuple[list[KnowledgeBase], int]:
        values = [item for item in self.bases.values() if item.user_id == user_id]
        start = (current - 1) * size
        return values[start : start + size], len(values)

    async def delete_base_for_user(self, base_id: UUID, user_id: UUID) -> bool:
        if await self.get_base_for_user(base_id, user_id) is None:
            return False
        del self.bases[base_id]
        for document_id in [
            item.id for item in self.documents.values() if item.knowledge_base_id == base_id
        ]:
            del self.documents[document_id]
        return True

    async def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        if await self.find_document_by_sha(document.knowledge_base_id, document.sha256):
            raise DuplicateKnowledgeDocumentError("This PDF is already imported")
        self.documents[document.id] = document
        return document

    async def find_document_by_sha(
        self, base_id: UUID, sha256: str
    ) -> KnowledgeDocument | None:
        return next(
            (
                item
                for item in self.documents.values()
                if item.knowledge_base_id == base_id and item.sha256 == sha256
            ),
            None,
        )

    async def get_document_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> KnowledgeDocument | None:
        item = self.documents.get(document_id)
        if item is None:
            return None
        return item if await self.get_base_for_user(item.knowledge_base_id, user_id) else None

    async def list_documents(
        self, base_id: UUID, current: int, size: int
    ) -> tuple[list[KnowledgeDocument], int]:
        values = [item for item in self.documents.values() if item.knowledge_base_id == base_id]
        start = (current - 1) * size
        return values[start : start + size], len(values)

    async def mark_processing(self, document_id: UUID) -> KnowledgeDocument:
        item = self.documents[document_id]
        item.status = DocumentStatus.PROCESSING
        item.processing_started_at = utc_now()
        item.attempt_count += 1
        item.updated_at = utc_now()
        return item

    async def claim_processing(
        self, document_id: UUID, stale_before: datetime, attempt: int = 1
    ) -> KnowledgeDocument | None:
        item = self.documents[document_id]
        if item.status == DocumentStatus.READY or item.status == DocumentStatus.FAILED:
            return None
        if item.status == DocumentStatus.PROCESSING:
            retry_claim = item.attempt_count == max(attempt - 1, 0)
            stale_claim = (
                item.processing_started_at is None
                or item.processing_started_at < stale_before
            )
            if not retry_claim and not stale_claim:
                return None
        item.status = DocumentStatus.PROCESSING
        item.processing_started_at = utc_now()
        item.attempt_count += 1
        item.updated_at = item.processing_started_at
        return item

    async def mark_ready(
        self, document_id: UUID, page_count: int, chunk_count: int
    ) -> KnowledgeDocument:
        item = self.documents[document_id]
        item.status = DocumentStatus.READY
        item.page_count = page_count
        item.chunk_count = chunk_count
        item.completed_at = utc_now()
        item.updated_at = item.completed_at
        item.failure_code = None
        item.failure_message = None
        return item

    async def mark_failed(
        self, document_id: UUID, error_code: str, error_message: str
    ) -> KnowledgeDocument:
        item = self.documents[document_id]
        item.status = DocumentStatus.FAILED
        item.error_code = error_code
        item.error_message = error_message
        item.failure_code = error_code
        item.failure_message = error_message
        item.updated_at = utc_now()
        return item

    async def delete_document_for_user(self, document_id: UUID, user_id: UUID) -> bool:
        if await self.get_document_for_user(document_id, user_id) is None:
            return False
        del self.documents[document_id]
        return True


class DeferredDocumentQueue:
    def __init__(self, error: Exception | None = None) -> None:
        self.jobs: list[DocumentImportJob] = []
        self.error = error

    def bind_inline_handler(self, handler: DocumentImportHandler) -> None:
        del handler

    async def enqueue_document(self, job: DocumentImportJob) -> None:
        self.jobs.append(job)
        if self.error is not None:
            raise self.error


class FakeVectorStore:
    def __init__(self) -> None:
        self.chunks: dict[UUID, list[StoredChunk]] = {}
        self.deleted: list[UUID] = []
        self.rollback_count = 0

    async def store_chunks(self, document_id: UUID, chunks: Sequence[StoredChunk]) -> None:
        self.chunks[document_id] = list(chunks)

    async def delete_document(self, document_id: UUID) -> None:
        self.chunks.pop(document_id, None)
        self.deleted.append(document_id)

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def similarity_search(
        self, document_id: UUID, embedding: Sequence[float], limit: int = 5
    ) -> Sequence[StoredChunk]:
        del embedding
        return self.chunks.get(document_id, [])[:limit]


@pytest.fixture
def knowledge_client() -> Iterator[
    tuple[
        TestClient,
        FakeUserRepository,
        FakeKnowledgeRepository,
        FakeFileStorage,
        FakePdfParser,
        FakeEmbedding,
        FakeVectorStore,
        Settings,
    ]
]:
    users = FakeUserRepository()
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser((PdfPage(1, "第一页内容"), PdfPage(2, "第二页内容")))
    embedding = FakeEmbedding()
    vector_store = FakeVectorStore()
    settings = Settings(
        rag_chunk_size=100,
        rag_chunk_overlap=2,
        rag_max_chunks_per_document=100,
        embedding_batch_size=2,
        knowledge_max_file_size=100,
    )
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_session_store] = lambda: FakeSessionStore()
    app.dependency_overrides[get_knowledge_repository] = lambda: repository
    app.dependency_overrides[get_file_storage] = lambda: storage
    app.dependency_overrides[get_pdf_parser] = lambda: parser
    app.dependency_overrides[get_embedding] = lambda: embedding
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_document_task_queue] = lambda: InlineDocumentTaskQueue()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_text_splitter] = lambda: SimpleTextSplitter(100, 2)
    with TestClient(app) as client:
        yield client, users, repository, storage, parser, embedding, vector_store, settings
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str, email: str) -> str:
    assert client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "secure-password"},
    ).status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        json={"account": email, "password": "secure-password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def create_base(client: TestClient, token: str, name: str = "Docs") -> str:
    response = client.post(
        "/api/xunzhi/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload(client: TestClient, token: str, base_id: str, content: bytes = b"%PDF-1.7 text"):
    return client.post(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("..\\resume.pdf", content, "application/pdf")},
    )


def test_knowledge_base_creation_duplicate_and_user_isolation(knowledge_client) -> None:
    client, _, _, _, _, _, _, _ = knowledge_client
    first = register_and_login(client, "kb-one", "kb-one@example.com")
    second = register_and_login(client, "kb-two", "kb-two@example.com")
    base_id = create_base(client, first)
    duplicate = client.post(
        "/api/xunzhi/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {first}"},
        json={"name": "Docs"},
    )
    same_name_other_user = client.post(
        "/api/xunzhi/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {second}"},
        json={"name": "Docs"},
    )
    forbidden = client.get(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}",
        headers={"Authorization": f"Bearer {second}"},
    )
    forbidden_delete = client.delete(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}",
        headers={"Authorization": f"Bearer {second}"},
    )
    assert duplicate.status_code == 409
    assert same_name_other_user.status_code == 201
    assert forbidden.status_code == forbidden_delete.status_code == 404


def test_upload_pdf_ready_pages_batches_and_safe_filename(knowledge_client) -> None:
    client, _, repository, storage, parser, embedding, vector_store, _ = knowledge_client
    token = register_and_login(client, "upload", "upload@example.com")
    base_id = create_base(client, token)
    response = upload(client, token, base_id)
    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "PENDING"
    assert body["page_count"] == 0
    assert body["safe_filename"].endswith(".pdf")
    assert "storage_path" not in body
    document = next(iter(repository.documents.values()))
    assert document.status == DocumentStatus.READY
    assert document.original_filename == "resume.pdf"
    assert document.storage_path not in body.values()
    assert parser.calls == 1
    assert embedding.batch_calls
    assert document.id in vector_store.chunks
    assert len(storage.files) == 1
    assert [chunk.page_number for chunk in vector_store.chunks[document.id]] == [1, 2]


@pytest.mark.asyncio
async def test_upload_returns_pending_without_processing_in_api_process() -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser((PdfPage(1, "queued text"),))
    vector_store = FakeVectorStore()
    queue = DeferredDocumentQueue()
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(100, 1),
        FakeEmbedding(),
        vector_store,
        queue,
        Settings(_env_file=None),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000005")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))

    document = await service.upload_document(
        user_id, base.id, "queued.pdf", "application/pdf", b"%PDF-1.7 queued"
    )

    assert document.status == DocumentStatus.PENDING
    assert parser.calls == 0
    assert not vector_store.chunks
    assert len(queue.jobs) == 1

    await service.process_document_job(queue.jobs[0])
    assert repository.documents[document.id].status == DocumentStatus.READY


def test_upload_endpoint_returns_pending_without_processing(knowledge_client) -> None:
    client, _, _, _, parser, _, _, _ = knowledge_client
    token = register_and_login(client, "queued-api", "queued-api@example.com")
    base_id = create_base(client, token)
    queue = DeferredDocumentQueue()
    app.dependency_overrides[get_document_task_queue] = lambda: queue

    response = upload(client, token, base_id)

    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"
    assert parser.calls == 0
    assert len(queue.jobs) == 1


@pytest.mark.asyncio
async def test_queue_failure_marks_document_failed_and_removes_file() -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    queue = DeferredDocumentQueue(RuntimeError("redis unavailable"))
    service = KnowledgeService(
        repository,
        storage,
        FakePdfParser(),
        SimpleTextSplitter(100, 1),
        FakeEmbedding(),
        FakeVectorStore(),
        queue,
        Settings(_env_file=None),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000006")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))

    with pytest.raises(KnowledgeQueueUnavailableError):
        await service.upload_document(
            user_id, base.id, "queued.pdf", "application/pdf", b"%PDF-1.7 queued"
        )

    document = next(iter(repository.documents.values()))
    assert document.status == DocumentStatus.FAILED
    assert document.failure_code == "QUEUE_UNAVAILABLE"
    assert storage.deleted
    assert not storage.files


@pytest.mark.asyncio
async def test_duplicate_document_job_does_not_reprocess_chunks() -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser((PdfPage(1, "duplicate-safe"),))
    vector_store = FakeVectorStore()
    queue = DeferredDocumentQueue()
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(100, 1),
        FakeEmbedding(),
        vector_store,
        queue,
        Settings(_env_file=None),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000007")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))
    document = await service.upload_document(
        user_id, base.id, "duplicate.pdf", "application/pdf", b"%PDF-1.7 duplicate"
    )

    await service.process_document_job(queue.jobs[0])
    first_chunks = list(vector_store.chunks[document.id])
    await service.process_document_job(queue.jobs[0])

    assert parser.calls == 1
    assert vector_store.chunks[document.id] == first_chunks


@pytest.mark.asyncio
async def test_concurrent_document_jobs_only_one_claims_document() -> None:
    class BlockingPdfParser(FakePdfParser):
        def __init__(self) -> None:
            super().__init__((PdfPage(1, "concurrent-safe"),))
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def parse(self, path: str) -> Sequence[PdfPage]:
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return self.pages

    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = BlockingPdfParser()
    queue = DeferredDocumentQueue()
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(100, 1),
        FakeEmbedding(),
        FakeVectorStore(),
        queue,
        Settings(_env_file=None),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000008")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))
    await service.upload_document(
        user_id, base.id, "concurrent.pdf", "application/pdf", b"%PDF-1.7 concurrent"
    )

    first = asyncio.create_task(service.process_document_job(queue.jobs[0]))
    await parser.started.wait()
    await service.process_document_job(queue.jobs[0])
    parser.release.set()
    await first

    assert parser.calls == 1
    assert next(iter(repository.documents.values())).status == DocumentStatus.READY


def test_non_pdf_mime_header_and_size_are_rejected(knowledge_client) -> None:
    client, _, _, _, _, _, _, _ = knowledge_client
    token = register_and_login(client, "validate", "validate@example.com")
    base_id = create_base(client, token)
    bad_extension = client.post(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.txt", b"%PDF-1.7", "application/pdf")},
    )
    bad_mime = client.post(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.pdf", b"%PDF-1.7", "text/plain")},
    )
    bad_header = client.post(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.pdf", b"not-a-pdf", "application/pdf")},
    )
    too_large = client.post(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.pdf", b"%PDF-" + b"x" * 200, "application/pdf")},
    )
    assert [
        item.status_code for item in (bad_extension, bad_mime, bad_header, too_large)
    ] == [400] * 4


def test_duplicate_document_and_document_delete_cleanup(knowledge_client) -> None:
    client, _, _, storage, _, _, vector_store, _ = knowledge_client
    token = register_and_login(client, "duplicate", "duplicate@example.com")
    base_id = create_base(client, token)
    first = upload(client, token, base_id)
    second = upload(client, token, base_id)
    document_id = first.json()["id"]
    deleted = client.delete(
        f"/api/xunzhi/v1/knowledge-documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert deleted.status_code == 200
    assert not vector_store.chunks
    assert storage.deleted


def test_document_list_and_owner_isolation(knowledge_client) -> None:
    client, _, _, _, _, _, _, _ = knowledge_client
    owner = register_and_login(client, "doc-owner", "doc-owner@example.com")
    other = register_and_login(client, "doc-other", "doc-other@example.com")
    base_id = create_base(client, owner)
    document = upload(client, owner, base_id)
    document_id = document.json()["id"]

    listed = client.get(
        f"/api/xunzhi/v1/knowledge-bases/{base_id}/documents?current=1&size=10",
        headers={"Authorization": f"Bearer {owner}"},
    )
    other_get = client.get(
        f"/api/xunzhi/v1/knowledge-documents/{document_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    other_delete = client.delete(
        f"/api/xunzhi/v1/knowledge-documents/{document_id}",
        headers={"Authorization": f"Bearer {other}"},
    )

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["records"][0]["id"] == document_id
    assert other_get.status_code == other_delete.status_code == 404


@pytest.mark.parametrize("error", ["empty", "encrypted"])
def test_pdf_parse_failures_mark_document_failed_and_cleanup(knowledge_client, error: str) -> None:
    client, _, repository, storage, parser, _, vector_store, _ = knowledge_client
    from app.modules.knowledge.exceptions import InvalidPdfError, UnsupportedPdfError

    parser.error = (
        InvalidPdfError("PDF text extraction failed")
        if error == "empty"
        else UnsupportedPdfError("Encrypted PDF files are not supported")
    )
    token = register_and_login(client, f"parse-{error}", f"parse-{error}@example.com")
    base_id = create_base(client, token)
    response = upload(client, token, base_id)
    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "PENDING"
    document = next(iter(repository.documents.values()))
    assert document.status == DocumentStatus.FAILED
    assert document.error_code
    assert not vector_store.chunks
    assert not storage.deleted


@pytest.mark.asyncio
async def test_chunk_limit_marks_failed_and_rolls_back() -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser((PdfPage(1, "long text"),))
    vector_store = FakeVectorStore()
    settings = Settings(rag_max_chunks_per_document=1)
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(4, 1),
        FakeEmbedding(),
        vector_store,
        InlineDocumentTaskQueue(),
        settings,
    )
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))
    await service.upload_document(
        user_id, base.id, "file.pdf", "application/pdf", b"%PDF-1.7 content"
    )
    document = repository.documents[next(iter(repository.documents))]
    assert document.status == DocumentStatus.FAILED
    assert document.error_code == "CHUNK_LIMIT_EXCEEDED"
    assert not vector_store.chunks
    assert not storage.deleted


def _embedding_test_chunks(count: int) -> tuple[TextChunk, ...]:
    return tuple(
        TextChunk(
            chunk_index=index,
            page_number=index + 1,
            content=f"synthetic chunk {index}",
            token_count=3,
            content_hash=f"hash-{index}",
        )
        for index in range(count)
    )


def _embedding_test_service(embedding: FakeEmbedding) -> KnowledgeService:
    return KnowledgeService(
        FakeKnowledgeRepository(),
        FakeFileStorage(),
        FakePdfParser(),
        SimpleTextSplitter(100, 1),
        embedding,
        FakeVectorStore(),
        InlineDocumentTaskQueue(),
        Settings(_env_file=None, embedding_batch_size=10),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("count", "expected_batches"),
    [(0, []), (1, [1]), (10, [10]), (11, [10, 1]), (26, [10, 10, 6])],
)
async def test_embedding_batches_respect_provider_safe_batch_size(
    count: int, expected_batches: list[int]
) -> None:
    embedding = FakeEmbedding()
    stored = await _embedding_test_service(embedding)._embed_chunks(_embedding_test_chunks(count))

    assert [len(batch) for batch in embedding.batch_calls] == expected_batches
    assert [chunk.content for chunk in stored] == [
        f"synthetic chunk {index}" for index in range(count)
    ]
    assert len(stored) == count
    assert all(len(chunk.embedding) == 1536 for chunk in stored)


@pytest.mark.asyncio
async def test_embedding_service_honors_adapter_batch_capability() -> None:
    class CappedEmbedding(FakeEmbedding):
        @property
        def max_batch_size(self) -> int:
            return 3

    embedding = CappedEmbedding()

    await _embedding_test_service(embedding)._embed_chunks(_embedding_test_chunks(8))

    assert [len(batch) for batch in embedding.batch_calls] == [3, 3, 2]


@pytest.mark.asyncio
async def test_embedding_second_batch_failure_retries_then_marks_document_failed() -> None:
    class FailOnSecondBatch(FakeEmbedding):
        async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
            self.batch_calls.append(tuple(texts))
            if len(self.batch_calls) == 2:
                raise RuntimeError("provider request failed")
            return [self._embed(text, self.dimensions) for text in texts]

    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser(tuple(PdfPage(index + 1, f"page {index}") for index in range(26)))
    vector_store = FakeVectorStore()
    embedding = FailOnSecondBatch()
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(100, 1),
        embedding,
        vector_store,
        InlineDocumentTaskQueue(),
        Settings(_env_file=None, embedding_batch_size=10),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000003")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))

    await service.upload_document(
        user_id, base.id, "file.pdf", "application/pdf", b"%PDF-1.7 content"
    )
    document = repository.documents[next(iter(repository.documents))]

    assert [len(batch) for batch in embedding.batch_calls] == [10, 10, 10, 10, 6]
    assert document.status == DocumentStatus.READY
    assert document.error_code is None
    assert vector_store.rollback_count == 1
    assert len(vector_store.chunks[document.id]) == 26
    assert not storage.deleted


@pytest.mark.asyncio
async def test_embedding_result_count_mismatch_is_rejected() -> None:
    class MissingVectorEmbedding(FakeEmbedding):
        async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
            self.batch_calls.append(tuple(texts))
            return [self._embed(texts[0], self.dimensions)]

    with pytest.raises(EmbeddingDimensionError, match="result count"):
        await _embedding_test_service(MissingVectorEmbedding())._embed_chunks(
            _embedding_test_chunks(2)
        )


@pytest.mark.asyncio
async def test_more_than_ten_pdf_chunks_reach_ready_with_ordered_batches() -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser(tuple(PdfPage(index + 1, f"page {index}") for index in range(26)))
    vector_store = FakeVectorStore()
    embedding = FakeEmbedding()
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(100, 1),
        embedding,
        vector_store,
        InlineDocumentTaskQueue(),
        Settings(_env_file=None, embedding_batch_size=10),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000004")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))

    await service.upload_document(
        user_id, base.id, "file.pdf", "application/pdf", b"%PDF-1.7 content"
    )
    document = repository.documents[next(iter(repository.documents))]

    assert document.status == DocumentStatus.READY
    assert document.chunk_count == 26
    assert [len(batch) for batch in embedding.batch_calls] == [10, 10, 6]
    assert [chunk.page_number for chunk in vector_store.chunks[document.id]] == list(
        range(1, 27)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_dimensions", [None, 3])
async def test_embedding_failure_or_dimension_marks_failed(
    wrong_dimensions: int | None,
) -> None:
    repository = FakeKnowledgeRepository()
    storage = FakeFileStorage()
    parser = FakePdfParser((PdfPage(1, "some text"),))
    vector_store = FakeVectorStore()
    embedding = FakeEmbedding(wrong_dimensions=wrong_dimensions)
    if wrong_dimensions is None:
        embedding.error = RuntimeError("provider secret")
    service = KnowledgeService(
        repository,
        storage,
        parser,
        SimpleTextSplitter(100, 1),
        embedding,
        vector_store,
        InlineDocumentTaskQueue(),
        Settings(),
    )
    user_id = UUID("00000000-0000-0000-0000-000000000002")
    base = await repository.create_base(KnowledgeBase.new(user_id, "base"))
    await service.upload_document(
        user_id, base.id, "file.pdf", "application/pdf", b"%PDF-1.7 content"
    )
    document = repository.documents[next(iter(repository.documents))]
    assert document.status == DocumentStatus.FAILED
    assert document.error_code in {"RETRY_EXHAUSTED", "EMBEDDING_DIMENSIONS_INVALID"}
    assert len(embedding.batch_calls) == (3 if wrong_dimensions is None else 1)
    assert not vector_store.chunks
    assert not storage.deleted


def test_splitter_is_page_aware_stable_and_clean() -> None:
    splitter = SimpleTextSplitter(chunk_size=8, chunk_overlap=2)
    first = splitter.split((PdfPage(2, "  第二页\r\n\r\n内容  "), PdfPage(1, "第一页")))
    second = splitter.split((PdfPage(2, "  第二页\r\n\r\n内容  "), PdfPage(1, "第一页")))
    assert first == second
    assert first[0].page_number == 2
    assert first[-1].page_number == 1
    assert all(chunk.content and chunk.token_count > 0 for chunk in first)


def test_knowledge_requires_authentication(knowledge_client) -> None:
    client, _, _, _, _, _, _, _ = knowledge_client
    response = client.get("/api/xunzhi/v1/knowledge-bases")
    assert response.status_code == 401
