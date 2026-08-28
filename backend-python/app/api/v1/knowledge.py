from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.domain import User
from app.modules.knowledge.dependencies import get_knowledge_service
from app.modules.knowledge.schemas import (
    DeleteResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeDocumentResponse,
    PageResponse,
)
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(prefix="/xunzhi/v1", tags=["knowledge"])


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeBaseResponse:
    base = await service.create_base(current_user.id, payload.name, payload.description)
    return KnowledgeBaseResponse.from_domain(base)


@router.get("/knowledge-bases", response_model=PageResponse[KnowledgeBaseResponse])
async def list_knowledge_bases(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
) -> PageResponse[KnowledgeBaseResponse]:
    bases, total = await service.list_bases(current_user.id, current, size)
    return PageResponse.build(
        [KnowledgeBaseResponse.from_domain(base) for base in bases], total, current, size
    )


@router.get("/knowledge-bases/{base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    base_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeBaseResponse:
    base = await service.get_base(current_user.id, base_id)
    return KnowledgeBaseResponse.from_domain(base)


@router.delete("/knowledge-bases/{base_id}", response_model=DeleteResponse)
async def delete_knowledge_base(
    base_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> DeleteResponse:
    await service.delete_base(current_user.id, base_id)
    return DeleteResponse(message="Knowledge base deleted")


@router.post(
    "/knowledge-bases/{base_id}/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    base_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(...)],
) -> KnowledgeDocumentResponse:
    content = await file.read(settings.knowledge_max_file_size + 1)
    document = await service.upload_document(
        current_user.id,
        base_id,
        file.filename or "document.pdf",
        file.content_type or "",
        content,
    )
    return KnowledgeDocumentResponse.from_domain(document)


@router.get(
    "/knowledge-bases/{base_id}/documents",
    response_model=PageResponse[KnowledgeDocumentResponse],
)
async def list_documents(
    base_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
) -> PageResponse[KnowledgeDocumentResponse]:
    documents, total = await service.list_documents(current_user.id, base_id, current, size)
    return PageResponse.build(
        [KnowledgeDocumentResponse.from_domain(document) for document in documents],
        total,
        current,
        size,
    )


@router.get(
    "/knowledge-documents/{document_id}", response_model=KnowledgeDocumentResponse
)
async def get_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> KnowledgeDocumentResponse:
    document = await service.get_document(current_user.id, document_id)
    return KnowledgeDocumentResponse.from_domain(document)


@router.delete("/knowledge-documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> DeleteResponse:
    await service.delete_document(current_user.id, document_id)
    return DeleteResponse(message="Knowledge document deleted")
