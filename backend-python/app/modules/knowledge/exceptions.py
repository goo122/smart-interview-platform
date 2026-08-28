from app.core.exceptions import AppError


class KnowledgeBaseNotFoundError(AppError):
    status_code = 404
    code = "knowledge_base_not_found"


class KnowledgeDocumentNotFoundError(AppError):
    status_code = 404
    code = "knowledge_document_not_found"


class KnowledgeNameAlreadyExistsError(AppError):
    status_code = 409
    code = "knowledge_base_name_exists"


class DuplicateKnowledgeDocumentError(AppError):
    status_code = 409
    code = "knowledge_document_exists"


class InvalidPdfError(AppError):
    status_code = 400
    code = "invalid_pdf"


class UnsupportedPdfError(AppError):
    status_code = 400
    code = "unsupported_pdf"


class KnowledgeImportError(AppError):
    status_code = 422
    code = "knowledge_import_failed"


class ChunkLimitExceededError(KnowledgeImportError):
    code = "CHUNK_LIMIT_EXCEEDED"


class EmbeddingDimensionError(KnowledgeImportError):
    code = "EMBEDDING_DIMENSIONS_INVALID"


class InvalidKnowledgeBaseError(AppError):
    status_code = 400
    code = "invalid_knowledge_base"
