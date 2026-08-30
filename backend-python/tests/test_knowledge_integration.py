import asyncio
import os
from collections.abc import AsyncIterator
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
import pytest_asyncio
from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.embedding import FakeEmbedding
from app.ai.evaluation import FakeInterviewAnswerEvaluator, StructuredInterviewEvaluation
from app.ai.followup import FakeFollowUpQuestionGenerator
from app.ai.interview import FakeInterviewQuestionGenerator
from app.ai.report import FakeInterviewReportNarrativeGenerator
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
from app.modules.interview.answer_service import InterviewAnswerService
from app.modules.interview.context import (
    InterviewContextProvider,
    InterviewEvaluationContextProvider,
)
from app.modules.interview.domain import (
    InterviewDifficulty,
    InterviewSession,
    InterviewStatus,
    InterviewType,
    TurnStatus,
)
from app.modules.interview.models import (
    InterviewAnswerModel,
    InterviewEvaluationModel,
    InterviewQuestionModel,
    InterviewSessionModel,
    InterviewTurnModel,
)
from app.modules.interview.repository import SqlAlchemyInterviewRepository
from app.modules.interview.service import InterviewService
from app.modules.knowledge.context import ContextAssembler, ContextCitation
from app.modules.knowledge.domain import (
    DocumentStatus,
    KnowledgeBase,
    KnowledgeDocument,
    PdfPage,
    StoredChunk,
)
from app.modules.knowledge.models import (
    KnowledgeBaseModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)
from app.modules.knowledge.repository import SqlAlchemyKnowledgeRepository
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter
from app.modules.report.models import InterviewReportModel
from app.modules.report.repository import SqlAlchemyInterviewReportRepository
from app.modules.report.service import InterviewReportService
from app.workers.queue import (
    DocumentImportJob,
    InlineDocumentTaskQueue,
    InlineTaskQueue,
    InterviewPreparationJob,
)
from app.workers.redis_queue import enqueue_document_job, enqueue_interview_preparation_job

pytestmark = pytest.mark.integration


def _database_url() -> str | None:
    return os.getenv("KNOWLEDGE_TEST_DATABASE_URL") or os.getenv("APP_DATABASE_URL")


def _redis_url() -> str | None:
    return os.getenv("KNOWLEDGE_TEST_REDIS_URL") or os.getenv("APP_REDIS_URL")


def _integration_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION_TESTS") == "1"


def _synthetic_pdf() -> bytes:
    content = "BT /F1 18 Tf 72 720 Td (Worker integration text) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf.encode("ascii")))
        pdf += f"{index} 0 obj\n{obj}\nendobj\n"
    xref_offset = len(pdf.encode("ascii"))
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    pdf += "".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    )
    return pdf.encode("ascii")


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    if not _integration_enabled():
        pytest.fail(
            "Integration tests require RUN_INTEGRATION_TESTS=1 and the dedicated test runner"
        )
    url = _database_url()
    if not url:
        pytest.fail("KNOWLEDGE_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.connect():
            pass
    except Exception as exc:
        await engine.dispose()
        pytest.fail(f"PostgreSQL integration service is not reachable: {type(exc).__name__}")
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    if not _integration_enabled():
        pytest.fail(
            "Integration tests require RUN_INTEGRATION_TESTS=1 and the dedicated test runner"
        )
    url = _redis_url()
    if not url:
        pytest.fail("KNOWLEDGE_TEST_REDIS_URL is not configured")
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        pytest.fail(f"Redis integration service is not reachable: {type(exc).__name__}")
    try:
        yield client
    finally:
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
            InlineDocumentTaskQueue(),
            Settings(knowledge_storage_dir=storage_dir.name),
        )
        document = await service.upload_document(
            user_id,
            base.id,
            "../resume.pdf",
            "application/pdf",
            b"%PDF-1.7 integration",
        )
        assert document.status == DocumentStatus.PENDING
        processed = await repository.get_document_for_user(document.id, user_id)
        assert processed is not None
        assert processed.status == DocumentStatus.READY
        assert processed.page_count == 2
        assert processed.chunk_count == 2
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
async def test_arq_worker_consumes_shared_storage_document(
    database_session: AsyncSession,
    redis_client: Redis,
) -> None:
    session = database_session
    user_id = uuid4()
    storage = LocalFileStorage(os.getenv("APP_KNOWLEDGE_STORAGE_DIR", "/app/storage"))
    repository = SqlAlchemyKnowledgeRepository(session)
    arq_redis = await create_pool(
        RedisSettings.from_dsn(_redis_url() or "redis://redis:6379/0"),
        default_queue_name="knowledge:documents",
    )
    document: KnowledgeDocument | None = None
    try:
        session.add(
            UserModel(
                id=user_id,
                username=f"worker-{user_id.hex[:8]}",
                email=f"worker-{user_id.hex[:8]}@example.com",
                password_hash="test-only",
                is_active=True,
            )
        )
        await session.commit()
        base = await repository.create_base(KnowledgeBase.new(user_id, "Worker"))
        pdf = _synthetic_pdf()
        stored = await storage.save_pdf(pdf)
        document = await repository.create_document(
            KnowledgeDocument.new(
                base.id,
                "worker.pdf",
                stored.safe_filename,
                "application/pdf",
                len(pdf),
                "worker-test-" + user_id.hex,
                stored.path,
            )
        )
        await enqueue_document_job(
            arq_redis,
            DocumentImportJob(document.id, user_id, base.id, f"worker-test:{user_id}"),
        )

        deadline = asyncio.get_running_loop().time() + 60
        while asyncio.get_running_loop().time() < deadline:
            await session.rollback()
            current = await repository.get_document_for_user(document.id, user_id)
            if current is not None and current.status == DocumentStatus.READY:
                break
            await asyncio.sleep(1)
        else:
            current = await repository.get_document_for_user(document.id, user_id)
            pytest.fail(f"Worker did not finish document import: {current}")

        assert current is not None
        assert current.status == DocumentStatus.READY
        assert current.page_count == 1
        assert current.chunk_count == 1
        count = await session.scalar(
            select(func.count())
            .select_from(KnowledgeChunkModel)
            .where(KnowledgeChunkModel.document_id == document.id)
        )
        assert count == 1
        assert await redis_client.ping()
    finally:
        await arq_redis.aclose()
        if document is not None:
            await storage.delete(document.storage_path)
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_arq_worker_prepares_interview_and_persists_ready_state(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id, base_id, document_id = uuid4(), uuid4(), uuid4()
    embedding = FakeEmbedding()
    query_text = (
        "岗位：Python 后端工程师\n岗位描述：负责 FastAPI 和 PostgreSQL\n"
        "难度：MEDIUM\n题目数：3"
    )
    vector = embedding._embed(query_text, embedding.dimensions)
    arq_redis = await create_pool(
        RedisSettings.from_dsn(_redis_url() or "redis://redis:6379/0"),
        default_queue_name="knowledge:documents",
    )
    try:
        session.add_all(
            [
                UserModel(
                    id=user_id,
                    username=f"interview-worker-{user_id.hex[:8]}",
                    email=f"interview-worker-{user_id.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                KnowledgeBaseModel(id=base_id, user_id=user_id, name="Interview Worker"),
                KnowledgeDocumentModel(
                    id=document_id,
                    knowledge_base_id=base_id,
                    original_filename="resume.pdf",
                    safe_filename="resume.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/interview-worker-resume.pdf",
                    status=DocumentStatus.READY.value,
                    page_count=1,
                    chunk_count=1,
                ),
            ]
        )
        await session.flush()
        session.add(
            KnowledgeChunkModel(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="FastAPI PostgreSQL 项目经验",
                token_count=4,
                content_hash=uuid4().hex * 2,
                embedding=vector,
            )
        )
        await session.commit()
        repository = SqlAlchemyInterviewRepository(session)
        interview = await repository.create(
            InterviewSession.new(
                user_id=user_id,
                knowledge_base_id=base_id,
                job_title="Python 后端工程师",
                job_description="负责 FastAPI 和 PostgreSQL",
                interview_type=InterviewType.TECHNICAL,
                difficulty=InterviewDifficulty.MEDIUM,
                question_count=3,
                request_id="worker-interview-1",
            )
        )
        queued, started = await repository.begin_preparing(interview.id, user_id)
        assert started
        assert queued.status == InterviewStatus.PREPARING
        await enqueue_interview_preparation_job(
            arq_redis,
            InterviewPreparationJob(interview.id, user_id, "worker-interview-1"),
        )

        deadline = asyncio.get_running_loop().time() + 60
        while asyncio.get_running_loop().time() < deadline:
            await session.rollback()
            current = await repository.get_for_user(interview.id, user_id)
            if current is not None and current.status == InterviewStatus.READY:
                break
            await asyncio.sleep(0.5)
        else:
            current = await repository.get_for_user(interview.id, user_id)
            pytest.fail(f"Worker did not prepare interview: {current}")

        assert current is not None
        assert current.status == InterviewStatus.READY
        questions = await repository.list_questions(interview.id)
        assert len(questions) == 3
        assert [event.to_status for event in await repository.list_events(interview.id)] == [
            InterviewStatus.CREATED,
            InterviewStatus.PREPARING,
            InterviewStatus.READY,
        ]
    finally:
        await arq_redis.aclose()
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


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
async def test_real_interview_preparation_retrieves_resume_generates_and_persists_questions(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id, base_id, document_id = uuid4(), uuid4(), uuid4()
    embedding = FakeEmbedding()
    settings = Settings(rag_similarity_threshold=0.0)
    query_text = (
        "岗位：Python 后端工程师\n岗位描述：负责 FastAPI 和 PostgreSQL\n"
        "难度：MEDIUM\n题目数：3"
    )
    vector = embedding._embed(query_text, embedding.dimensions)
    try:
        session.add_all(
            [
                UserModel(
                    id=user_id,
                    username=f"interview-{user_id.hex[:8]}",
                    email=f"interview-{user_id.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                KnowledgeBaseModel(id=base_id, user_id=user_id, name="Interview Resume"),
                KnowledgeDocumentModel(
                    id=document_id,
                    knowledge_base_id=base_id,
                    original_filename="resume.pdf",
                    safe_filename="resume.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/interview-resume.pdf",
                    status=DocumentStatus.READY.value,
                    page_count=1,
                    chunk_count=1,
                ),
            ]
        )
        await session.flush()
        session.add(
            KnowledgeChunkModel(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="FastAPI PostgreSQL 项目经验",
                token_count=4,
                content_hash=uuid4().hex * 2,
                embedding=vector,
            )
        )
        await session.commit()
        context_provider = InterviewContextProvider(
            SqlAlchemyKnowledgeRepository(session),
            embedding,
            PgVectorRetriever(session),
            ContextAssembler(200, 50),
            settings,
        )
        generator = FakeInterviewQuestionGenerator()
        service = InterviewService(
            SqlAlchemyInterviewRepository(session),
            context_provider,
            generator,
            InlineTaskQueue(),
            settings,
        )
        created = await service.create_session(
            user_id=user_id,
            knowledge_base_id=base_id,
            job_title="Python 后端工程师",
            job_description="负责 FastAPI 和 PostgreSQL",
            interview_type=InterviewType.TECHNICAL,
            difficulty=InterviewDifficulty.MEDIUM,
            question_count=3,
            request_id="prepare-once",
        )
        assert created.status == InterviewStatus.READY
        questions = await service.get_questions(user_id, created.id)
        assert len(questions) == 1
        all_questions = await SqlAlchemyInterviewRepository(session).list_questions(created.id)
        assert len(all_questions) == 3
        assert all_questions[0].citations[0].source_id == "[S1]"
        events = await SqlAlchemyInterviewRepository(session).list_events(created.id)
        assert [event.to_status for event in events] == [
            InterviewStatus.CREATED,
            InterviewStatus.PREPARING,
            InterviewStatus.READY,
        ]
        duplicate = await service.create_session(
            user_id=user_id,
            knowledge_base_id=base_id,
            job_title="Python 后端工程师",
            job_description="负责 FastAPI 和 PostgreSQL",
            interview_type=InterviewType.TECHNICAL,
            difficulty=InterviewDifficulty.MEDIUM,
            question_count=3,
            request_id="prepare-once",
        )
        assert duplicate.id == created.id
        assert generator.calls == 1
        started = await service.start(user_id, created.id)
        assert started.status == InterviewStatus.IN_PROGRESS
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_real_langgraph_answer_evaluation_follow_up_and_completion(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id, base_id, document_id = uuid4(), uuid4(), uuid4()
    embedding = FakeEmbedding()
    settings = Settings(rag_similarity_threshold=0.0, interview_min_answer_length=3)
    query_text = (
        "岗位：Python 后端工程师\n岗位描述：负责 FastAPI 和 PostgreSQL\n"
        "难度：MEDIUM\n题目数：3"
    )
    vector = embedding._embed(query_text, embedding.dimensions)
    try:
        session.add_all(
            [
                UserModel(
                    id=user_id,
                    username=f"answer-integration-{user_id.hex[:8]}",
                    email=f"answer-integration-{user_id.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                KnowledgeBaseModel(id=base_id, user_id=user_id, name="Answer Resume"),
                KnowledgeDocumentModel(
                    id=document_id,
                    knowledge_base_id=base_id,
                    original_filename="resume.pdf",
                    safe_filename="answer-resume.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    sha256=uuid4().hex * 2,
                    storage_path="/tmp/answer-resume.pdf",
                    status=DocumentStatus.READY.value,
                    page_count=1,
                    chunk_count=1,
                ),
            ]
        )
        await session.flush()
        session.add(
            KnowledgeChunkModel(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="FastAPI PostgreSQL 项目经验和性能指标",
                token_count=6,
                content_hash=uuid4().hex * 2,
                embedding=vector,
            )
        )
        await session.commit()
        retriever = PgVectorRetriever(session)
        context_provider = InterviewContextProvider(
            SqlAlchemyKnowledgeRepository(session),
            embedding,
            retriever,
            ContextAssembler(200, 50),
            settings,
        )
        interview_repository = SqlAlchemyInterviewRepository(session)
        prep_service = InterviewService(
            interview_repository,
            context_provider,
            FakeInterviewQuestionGenerator(),
            InlineTaskQueue(),
            settings,
        )
        created = await prep_service.create_session(
            user_id=user_id,
            knowledge_base_id=base_id,
            job_title="Python 后端工程师",
            job_description="负责 FastAPI 和 PostgreSQL",
            interview_type=InterviewType.TECHNICAL,
            difficulty=InterviewDifficulty.MEDIUM,
            question_count=3,
            request_id="answer-flow",
        )
        await prep_service.start(user_id, created.id)
        answer_service = InterviewAnswerService(
            interview_repository,
            InterviewEvaluationContextProvider(
                SqlAlchemyKnowledgeRepository(session),
                embedding,
                retriever,
                ContextAssembler(200, 50),
                settings,
            ),
            FakeInterviewAnswerEvaluator(
                output=StructuredInterviewEvaluation(
                    overall_score=40,
                    technical_score=40,
                    relevance_score=50,
                    clarity_score=50,
                    depth_score=30,
                    strengths=["有初步方案"],
                    weaknesses=["缺少取舍说明"],
                    feedback="需要进一步澄清技术取舍。",
                    suggested_improvements=["补充指标"],
                    should_follow_up=True,
                    follow_up_focus="技术取舍",
                )
            ),
            FakeFollowUpQuestionGenerator(),
            InlineTaskQueue(),
            settings,
        )
        first_turn = await answer_service.current_turn(user_id, created.id)
        await answer_service.submit_answer(
            user_id=user_id,
            session_id=created.id,
            turn_id=first_turn.turn.id,
            answer="我负责异步架构设计并验证了性能指标。",
            request_id="answer-flow-1",
        )
        follow_up = await answer_service.current_turn(user_id, created.id)
        assert follow_up.turn.status == TurnStatus.WAITING_ANSWER
        assert follow_up.turn.parent_turn_id == first_turn.turn.id
        first_completed = await answer_service.get_turn(user_id, first_turn.turn.id)
        assert first_completed.evaluation is not None

        evaluator = answer_service._workflow._evaluator
        assert isinstance(evaluator, FakeInterviewAnswerEvaluator)
        evaluator.output = StructuredInterviewEvaluation(
            overall_score=90,
            technical_score=90,
            relevance_score=90,
            clarity_score=90,
            depth_score=90,
            strengths=["回答完整"],
            weaknesses=["可继续量化"],
            feedback="回答完整。",
            suggested_improvements=["补充复盘"],
            should_follow_up=False,
        )
        await answer_service.submit_answer(
            user_id=user_id,
            session_id=created.id,
            turn_id=follow_up.turn.id,
            answer="我补充了技术取舍、边界和上线结果。",
            request_id="answer-flow-2",
        )
        next_turn = await answer_service.current_turn(user_id, created.id)
        assert next_turn.turn.question_id is not None
        await answer_service.submit_answer(
            user_id=user_id,
            session_id=created.id,
            turn_id=next_turn.turn.id,
            answer="第二题也完成了设计、实现和性能复盘。",
            request_id="answer-flow-3",
        )
        completed = await interview_repository.get_for_user(created.id, user_id)
        assert completed is not None
        assert completed.status == InterviewStatus.IN_PROGRESS
        final_turn = await answer_service.current_turn(user_id, created.id)
        await answer_service.submit_answer(
            user_id=user_id,
            session_id=created.id,
            turn_id=final_turn.turn.id,
            answer="我完成了最后一个方案并总结了风险与收益。",
            request_id="answer-flow-4",
        )
        completed = await interview_repository.get_for_user(created.id, user_id)
        assert completed is not None
        assert completed.status == InterviewStatus.COMPLETED
        events = await interview_repository.list_events(created.id)
        event_types = [event.event_type for event in events]
        assert "ANSWER_SUBMITTED" in event_types
        assert "ANSWER_EVALUATED" in event_types
        assert "FOLLOW_UP_CREATED" in event_types
        assert "INTERVIEW_COMPLETED" in event_types
    finally:
        await session.rollback()
        await session.execute(delete(UserModel).where(UserModel.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_report_generation_persists_deterministic_snapshot(
    database_session: AsyncSession,
) -> None:
    session = database_session
    user_id, base_id, session_id = uuid4(), uuid4(), uuid4()
    question_ids = [uuid4(), uuid4()]
    turn_ids = [uuid4(), uuid4()]
    now = chat_utc_now()
    try:
        session.add_all(
            [
                UserModel(
                    id=user_id,
                    username=f"report-integration-{user_id.hex[:8]}",
                    email=f"report-integration-{user_id.hex[:8]}@example.com",
                    password_hash="test-only",
                    is_active=True,
                ),
                KnowledgeBaseModel(id=base_id, user_id=user_id, name="Report Resume"),
            ]
        )
        await session.flush()
        session.add(
            InterviewSessionModel(
                    id=session_id,
                    user_id=user_id,
                    knowledge_base_id=base_id,
                    job_title="Python 工程师",
                    job_description="负责后端系统开发",
                    interview_type=InterviewType.TECHNICAL.value,
                    difficulty=InterviewDifficulty.MEDIUM.value,
                    question_count=3,
                    status=InterviewStatus.COMPLETED.value,
                    current_question_index=1,
                    version=5,
                    created_at=now,
                    updated_at=now,
                    started_at=now,
                    finished_at=now,
            )
        )
        await session.flush()
        session.add_all(
            [
                InterviewQuestionModel(
                    id=question_ids[0],
                    session_id=session_id,
                    sequence=1,
                    content="请说明系统方案",
                    category="TECHNICAL",
                    difficulty=InterviewDifficulty.MEDIUM.value,
                    expected_points=["架构"],
                    created_at=now,
                ),
                InterviewQuestionModel(
                    id=question_ids[1],
                    session_id=session_id,
                    sequence=2,
                    content="请说明上线结果",
                    category="TECHNICAL",
                    difficulty=InterviewDifficulty.MEDIUM.value,
                    expected_points=["指标"],
                    created_at=now,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                InterviewTurnModel(
                    id=turn_ids[0],
                    session_id=session_id,
                    question_id=question_ids[0],
                    sequence=1,
                    turn_type="PRIMARY",
                    question_content="请说明系统方案",
                    status="COMPLETED",
                    follow_up_depth=0,
                    created_at=now,
                    answered_at=now,
                    evaluated_at=now,
                ),
                InterviewTurnModel(
                    id=turn_ids[1],
                    session_id=session_id,
                    question_id=question_ids[1],
                    sequence=2,
                    turn_type="PRIMARY",
                    question_content="请说明上线结果",
                    status="COMPLETED",
                    follow_up_depth=0,
                    created_at=now,
                    answered_at=now,
                    evaluated_at=now,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                InterviewAnswerModel(
                    id=uuid4(),
                    turn_id=turn_ids[0],
                    session_id=session_id,
                    user_id=user_id,
                    content="我设计了异步架构并完成验证。",
                    request_id="report-integration-answer-1",
                    created_at=now,
                ),
                InterviewAnswerModel(
                    id=uuid4(),
                    turn_id=turn_ids[1],
                    session_id=session_id,
                    user_id=user_id,
                    content="上线后延迟降低并完成复盘。",
                    request_id="report-integration-answer-2",
                    created_at=now,
                ),
            ]
        )
        for turn_id, score in zip(turn_ids, (80, 60), strict=True):
            session.add(
                InterviewEvaluationModel(
                    id=uuid4(),
                    turn_id=turn_id,
                    overall_score=score,
                    technical_score=score,
                    relevance_score=score,
                    clarity_score=score,
                    depth_score=score,
                    strengths=["结构清晰"],
                    weaknesses=["补充指标"],
                    feedback="结构化反馈",
                    suggested_improvements=["补充复盘"],
                    llm_should_follow_up=False,
                    created_at=now,
                )
            )
        await session.commit()
        report_repository = SqlAlchemyInterviewReportRepository(session)
        narrative = FakeInterviewReportNarrativeGenerator()
        service = InterviewReportService(
            SqlAlchemyInterviewRepository(session),
            report_repository,
            narrative,
            InlineTaskQueue(),
            Settings(),
        )
        detail = await service.generate(user_id, session_id)
        repeated = await service.generate(user_id, session_id)
        assert detail.report.status.value == "READY"
        assert detail.report.overall_score == 70
        assert [item.sequence for item in detail.items] == [1, 2]
        assert repeated.report.id == detail.report.id
        assert narrative.calls == 1
        completed = await SqlAlchemyInterviewRepository(session).get_for_user(session_id, user_id)
        assert completed is not None
        assert completed.status == InterviewStatus.COMPLETED
    finally:
        await session.rollback()
        await session.execute(
            delete(InterviewReportModel).where(
                InterviewReportModel.session_id == session_id
            )
        )
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
