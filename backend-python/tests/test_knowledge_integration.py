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
from app.infrastructure.vectorstore.sqlalchemy import SqlAlchemyVectorStore
from app.modules.auth.models import UserModel
from app.modules.auth.session_store import RedisSessionStore
from app.modules.knowledge.domain import KnowledgeBase, PdfPage, StoredChunk
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
