from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding import EmbeddingPort
from app.core.config import Settings, get_settings
from app.infrastructure.storage.files import FileStoragePort
from app.infrastructure.storage.pdf import PdfParserPort
from app.infrastructure.vectorstore.port import VectorStorePort
from app.infrastructure.vectorstore.sqlalchemy import SqlAlchemyVectorStore
from app.modules.auth.dependencies import get_db_session
from app.modules.knowledge.repository import (
    KnowledgeRepository,
    SqlAlchemyKnowledgeRepository,
)
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.splitter import SimpleTextSplitter, TextSplitterPort
from app.workers.queue import TaskQueuePort


async def get_knowledge_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KnowledgeRepository:
    return SqlAlchemyKnowledgeRepository(session)


def get_file_storage(request: Request) -> FileStoragePort:
    return cast(FileStoragePort, request.app.state.file_storage)


def get_pdf_parser(request: Request) -> PdfParserPort:
    return cast(PdfParserPort, request.app.state.pdf_parser)


def get_text_splitter(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TextSplitterPort:
    return SimpleTextSplitter(settings.rag_chunk_size, settings.rag_chunk_overlap)


def get_embedding(request: Request) -> EmbeddingPort:
    return cast(EmbeddingPort, request.app.state.embedding)


def get_vector_store(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VectorStorePort:
    return SqlAlchemyVectorStore(session, settings.embedding_dimensions)


def get_task_queue(request: Request) -> TaskQueuePort:
    return cast(TaskQueuePort, request.app.state.task_queue)


def get_knowledge_service(
    repository: Annotated[KnowledgeRepository, Depends(get_knowledge_repository)],
    file_storage: Annotated[FileStoragePort, Depends(get_file_storage)],
    pdf_parser: Annotated[PdfParserPort, Depends(get_pdf_parser)],
    text_splitter: Annotated[TextSplitterPort, Depends(get_text_splitter)],
    embedding: Annotated[EmbeddingPort, Depends(get_embedding)],
    vector_store: Annotated[VectorStorePort, Depends(get_vector_store)],
    task_queue: Annotated[TaskQueuePort, Depends(get_task_queue)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeService:
    return KnowledgeService(
        repository,
        file_storage,
        pdf_parser,
        text_splitter,
        embedding,
        vector_store,
        task_queue,
        settings,
    )
