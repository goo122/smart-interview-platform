import os
from collections.abc import AsyncIterator
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.embedding import FakeEmbedding
from app.core.config import Settings
from app.infrastructure.storage.files import LocalFileStorage
from app.infrastructure.storage.pdf import FakePdfParser
from app.infrastructure.vectorstore.retriever import PgVectorRetriever
from app.infrastructure.vectorstore.sqlalchemy import SqlAlchemyVectorStore
from app.modules.auth.models import UserModel
from app.modules.auth.session_store import RedisSessionStore
from app.modules.chat.domain import MessageRole
from app.modules.chat.domain import utc_now as chat_utc_now
from app.modules.chat.models import ConversationModel, MessageCitationModel, MessageModel
from app.modules.chat.repository import SqlAlchemyMessageRepository
from app.modules.knowledge.context import ContextCitation
from app.modules.knowledge.domain import DocumentStatus, KnowledgeBase, PdfPage, StoredChunk
from app.modules.knowledge.models import (
    KnowledgeBaseModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)
from app.modules.knowledge.repository import SqlAlchemyKnowledgeRepository
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter
from app.workers.queue import InlineTaskQueue

pytestmark = pytest.mark.integration


def _database_url() -> str | None:
    return os.getenv("KNOWLEDGE_TEST_DATABASE_URL") or os.getenv("APP_DATABASE_URL")


def _redis_url() -> str | None:
    return os.getenv("KNOWLEDGE_TEST_REDIS_URL") or os.getenv("APP_REDIS_URL")


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    url = _database_url()
    if not url:
        pytest.skip("KNOWLEDGE_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    url = _redis_url()
    if not url:
        pytest.skip("KNOWLEDGE_TEST_REDIS_URL is not configured")
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip("Redis is not reachable")
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_pgvector_schema_write_similarity_and_foreign_keys(
    database_session: AsyncSession,
) -> None:
    session = database_session
    extension = await session.scalar(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    )
    assert extension
    vector_type = await session.scalar(
        text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'knowledge_chunks'::regclass AND attname = 'embedding'"
        )
    )
    assert vector_type == 1536

    user_id = uuid4()
    base_id = uuid4()
    document_id = uuid4()
    try:
        session.add(
            UserModel(
                id=user_id,
                username=f"integration-{user_id.hex[:8]}",
                email=f"integration-{user_id.hex[:8]}@example.com",
                password_hash="test-only",
                is_active=True,
            )
        )
        session.add(KnowledgeBaseModel(id=base_id, user_id=user_id, name="Integration"))
        session.add(
            KnowledgeDocumentModel(
                id=document_id,
                knowledge_base_id=base_id,
                original_filename="test.pdf",
                safe_filename="safe.pdf",
                content_type="application/pdf",
                size_bytes=10,
                sha256=uuid4().hex * 2,
                storage_path="/tmp/safe.pdf",
                status="READY",
                page_count=1,
                chunk_count=1,
            )
        )
        await session.flush()
        embedding = FakeEmbedding()
        vector = tuple(embedding._embed("integration chunk", embedding.dimensions))
        store = SqlAlchemyVectorStore(session)
        await store.store_chunks(
            document_id,
            [
                StoredChunk(
                    chunk_index=0,
                    page_number=1,
                    content="integration chunk",
                    token_count=4,
                    content_hash=uuid4().hex * 2,
                    embedding=vector,
                )
            ],
        )
        await session.commit()
        rows = await store.similarity_search(document_id, vector, limit=1)
        assert len(rows) == 1
        assert rows[0].content == "integration chunk"
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_postgres_unique_constraints_and_transaction_rollback(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id = uuid4()
    base_id = uuid4()
    try:
        session.add(
            UserModel(
                id=user_id,
                username=f"constraint-{user_id.hex[:8]}",
                email=f"constraint-{user_id.hex[:8]}@example.com",
                password_hash="test-only",
                is_active=True,
            )
        )
        session.add(KnowledgeBaseModel(id=base_id, user_id=user_id, name="Unique"))
        await session.commit()
        session.add(KnowledgeBaseModel(id=uuid4(), user_id=user_id, name="Unique"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        session.add(KnowledgeBaseModel(id=uuid4(), user_id=user_id, name="Rollback"))
        await session.flush()
        await session.rollback()
        count = await session.scalar(
            text(
                "SELECT count(*) FROM knowledge_bases "
                "WHERE user_id = :user_id AND name = 'Rollback'"
            ),
            {"user_id": user_id},
        )
        assert count == 0
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_pgvector_retrieval_scopes_user_base_status_topk_and_threshold(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_one, user_two = uuid4(), uuid4()
    base_one, base_two = uuid4(), uuid4()
    ready_one, ready_two, pending = uuid4(), uuid4(), uuid4()
    vector_a = [0.0] * 1536
    vector_a[0] = 1.0
    vector_b = [0.0] * 1536
    vector_b[0], vector_b[1] = 0.8, 0.6
    vector_other = [0.0] * 1536
    vector_other[0] = 1.0
    try:
        session.add_all(
            [
                UserModel(
                    id=user_one,
                    username=f"retrieve-{user_one.hex[:8]}",
                    email=f"retrieve-{user_one.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                UserModel(
                    id=user_two,
                    username=f"retrieve-{user_two.hex[:8]}",
                    email=f"retrieve-{user_two.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                KnowledgeBaseModel(id=base_one, user_id=user_one, name="One"),
                KnowledgeBaseModel(id=base_two, user_id=user_two, name="Two"),
            ]
        )
        session.add_all(
            [
                KnowledgeDocumentModel(
                    id=ready_one,
                    knowledge_base_id=base_one,
                    original_filename="one-best.pdf",
                    safe_filename="one-best.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/one-best.pdf",
                    status=DocumentStatus.READY.value,
                    page_count=1,
                    chunk_count=1,
                ),
                KnowledgeDocumentModel(
                    id=ready_two,
                    knowledge_base_id=base_one,
                    original_filename="one-second.pdf",
                    safe_filename="one-second.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/one-second.pdf",
                    status=DocumentStatus.READY.value,
                    page_count=1,
                    chunk_count=1,
                ),
                KnowledgeDocumentModel(
                    id=pending,
                    knowledge_base_id=base_one,
                    original_filename="pending.pdf",
                    safe_filename="pending.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/pending.pdf",
                    status=DocumentStatus.PROCESSING.value,
                    page_count=1,
                    chunk_count=1,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                KnowledgeChunkModel(
                    document_id=ready_one,
                    chunk_index=0,
                    page_number=1,
                    content="best",
                    token_count=1,
                    content_hash=uuid4().hex * 2,
                    embedding=vector_a,
                ),
                KnowledgeChunkModel(
                    document_id=ready_two,
                    chunk_index=0,
                    page_number=1,
                    content="second",
                    token_count=1,
                    content_hash=uuid4().hex * 2,
                    embedding=vector_b,
                ),
                KnowledgeChunkModel(
                    document_id=pending,
                    chunk_index=0,
                    page_number=1,
                    content="pending",
                    token_count=1,
                    content_hash=uuid4().hex * 2,
                    embedding=vector_other,
                ),
            ]
        )
        await session.commit()
        retriever = PgVectorRetriever(session)
        result = await retriever.retrieve(
            user_id=user_one,
            knowledge_base_id=base_one,
            query_vector=vector_a,
            top_k=5,
            similarity_threshold=0.75,
        )
        assert [item.content for item in result] == ["best", "second"]
        assert result[0].score > result[1].score
        strict = await retriever.retrieve(
            user_id=user_one,
            knowledge_base_id=base_one,
            query_vector=vector_a,
            top_k=5,
            similarity_threshold=0.85,
        )
        assert [item.content for item in strict] == ["best"]
        assert len(
            await retriever.retrieve(
                user_id=user_one,
                knowledge_base_id=base_one,
                query_vector=vector_a,
                top_k=1,
                similarity_threshold=0,
            )
        ) == 1
        assert not await retriever.retrieve(
            user_id=user_two,
            knowledge_base_id=base_one,
            query_vector=vector_a,
            top_k=5,
            similarity_threshold=0,
        )
        assert not await retriever.retrieve(
            user_id=user_two,
            knowledge_base_id=base_two,
            query_vector=vector_a,
            top_k=5,
            similarity_threshold=0,
        )
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id.in_([user_one, user_two])))
        await session.commit()


@pytest.mark.asyncio
async def test_real_postgres_import_pipeline_with_fake_parser_and_embedding(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id = uuid4()
    storage_dir = TemporaryDirectory()
    storage = LocalFileStorage(storage_dir.name)
    repository = SqlAlchemyKnowledgeRepository(session)
    vector_store = SqlAlchemyVectorStore(session)
    try:
        session.add(
            UserModel(
                id=user_id,
                username=f"pipeline-{user_id.hex[:8]}",
                email=f"pipeline-{user_id.hex[:8]}@example.com",
                password_hash="test-only",
                is_active=True,
            )
        )
        await session.commit()
        base = await repository.create_base(KnowledgeBase.new(user_id, "Pipeline"))
        service = KnowledgeService(
            repository,
            storage,
            FakePdfParser((PdfPage(1, "第一页文本"), PdfPage(2, "第二页文本"))),
            SimpleTextSplitter(100, 1),
            FakeEmbedding(),
            vector_store,
            InlineTaskQueue(),
            Settings(knowledge_storage_dir=storage_dir.name),
        )
        document = await service.upload_document(
            user_id,
            base.id,
            "../resume.pdf",
            "application/pdf",
            b"%PDF-1.7 integration",
        )
        assert document.status.value == "READY"
        assert document.page_count == 2
        assert document.chunk_count == 2
        count = await session.scalar(
            select(func.count()).select_from(KnowledgeChunkModel).where(
                KnowledgeChunkModel.document_id == document.id
            )
        )
        assert count == 2
        await storage.delete(document.storage_path)
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()
        storage_dir.cleanup()


@pytest.mark.asyncio
async def test_message_citations_persist_in_order_and_cascade_with_document(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id, base_id, document_id, chunk_id = uuid4(), uuid4(), uuid4(), uuid4()
    conversation_id, message_id = uuid4(), uuid4()
    try:
        session.add_all(
            [
                UserModel(
                    id=user_id,
                    username=f"citation-{user_id.hex[:8]}",
                    email=f"citation-{user_id.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                KnowledgeBaseModel(id=base_id, user_id=user_id, name="Citations"),
                KnowledgeDocumentModel(
                    id=document_id,
                    knowledge_base_id=base_id,
                    original_filename="resume.pdf",
                    safe_filename="resume.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/resume.pdf",
                    status=DocumentStatus.READY.value,
                    page_count=1,
                    chunk_count=1,
                ),
                ConversationModel(
                    id=conversation_id,
                    user_id=user_id,
                    title="citation chat",
                    status="ACTIVE",
                    created_at=chat_utc_now(),
                    updated_at=chat_utc_now(),
                ),
                MessageModel(
                    id=message_id,
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT.value,
                    content="pending",
                    status="PENDING",
                    sequence=1,
                    created_at=chat_utc_now(),
                ),
            ]
        )
        await session.commit()
        session.add(
            KnowledgeChunkModel(
                id=chunk_id,
                document_id=document_id,
                chunk_index=0,
                page_number=3,
                content="citation content",
                token_count=2,
                content_hash=uuid4().hex * 2,
                embedding=[0.0] * 1535 + [1.0],
            )
        )
        await session.commit()
        repository = SqlAlchemyMessageRepository(session)
        citation = ContextCitation(
            source_id="[S1]",
            chunk_id=chunk_id,
            document_id=document_id,
            document_name="resume.pdf",
            page_number=3,
            score=0.91,
            excerpt="citation content",
            ordinal=0,
        )
        completed = await repository.complete_with_citations(message_id, "answer", [citation])
        assert completed.status.value == "COMPLETED"
        assert completed.citations[0].document_name == "resume.pdf"
        history = await repository.list_for_conversation(conversation_id)
        assert history[0].citations[0].source_id == "[S1]"
        await session.execute(
            delete(KnowledgeDocumentModel).where(KnowledgeDocumentModel.id == document_id)
        )
        await session.commit()
        assert await session.scalar(
            select(func.count()).select_from(MessageCitationModel).where(
                MessageCitationModel.message_id == message_id
            )
        ) == 0
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_redis_read_write_ttl_and_auth_session_store(redis_client: Redis) -> None:
    key = f"knowledge-integration:{uuid4()}"
    await redis_client.set(key, "ok", ex=30)
    assert await redis_client.get(key) == "ok"
    assert 0 < (await redis_client.ttl(key)) <= 30

    store = RedisSessionStore(redis_client, revocation_ttl_seconds=30)
    refresh_id = uuid4()
    user_id = uuid4()
    await store.save_refresh_session(refresh_id, user_id, 30)
    assert await store.consume_refresh_session(refresh_id) == user_id
    assert await store.consume_refresh_session(refresh_id) is None
    await redis_client.delete(key)
