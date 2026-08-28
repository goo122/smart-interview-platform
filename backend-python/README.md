# AI Interview Backend

Minimal FastAPI foundation for the intelligent mock interview platform.

## Local development

```powershell
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Database migrations

Alembic reads `APP_DATABASE_URL` through the same Pydantic Settings used by the
application. Run migrations from this directory:

```powershell
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
```

The initial migration creates the `users` table. PostgreSQL is required for
applying migrations; the migration can also be inspected without a database by
running `uv run alembic upgrade head --sql`.

The chat slice adds migration `0002_create_conversations_and_messages`:

```powershell
uv run alembic upgrade head
uv run alembic heads
uv run alembic upgrade head --sql > migration.sql
```

## Authentication API

The versioned endpoints are:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

## Chat API

The endpoints retain the React application's existing `/api/xunzhi/v1/ai` prefix:

- `POST /api/xunzhi/v1/ai/conversations` with `{ "firstMessage": "..." }`
- `GET /api/xunzhi/v1/ai/conversations?current=1&size=10`
- `GET /api/xunzhi/v1/ai/conversations/{sessionId}`
- `POST` or `PUT /api/xunzhi/v1/ai/conversations/{sessionId}/end`
- `DELETE /api/xunzhi/v1/ai/conversations/{sessionId}`
- `GET /api/xunzhi/v1/ai/history/{sessionId}`
- `GET /api/xunzhi/v1/ai/history/page?sessionId=...&current=1&size=10`
- `POST /api/xunzhi/v1/ai/sessions/{sessionId}/chat`

Chat requests accept the legacy `{ "sessionId": "...", "inputMessage": "...", "userName": "..." }`
shape (the authenticated user is always authoritative). The chat endpoint returns
`text/event-stream` events in this order:

```text
event: start
data: {"conversation_id":"...","message_id":"..."}

event: delta
data: {"content":"增量文本"}

event: complete
data: {"message_id":"...","content":"完整文本"}
```

Generation failures return an `error` event with a generic message and mark the
assistant message as `FAILED`. With no model configuration the application still
starts and emits that safe failure event; tests inject `FakeChatModel` instead of
calling a real provider.

## PDF knowledge base import

Knowledge base and document endpoints use the `/api/xunzhi/v1` prefix and require
the existing Bearer access token:

- `POST /api/xunzhi/v1/knowledge-bases`
- `GET /api/xunzhi/v1/knowledge-bases?current=1&size=10`
- `GET /api/xunzhi/v1/knowledge-bases/{id}`
- `DELETE /api/xunzhi/v1/knowledge-bases/{id}`
- `POST /api/xunzhi/v1/knowledge-bases/{id}/documents` (multipart field `file`)
- `GET /api/xunzhi/v1/knowledge-bases/{id}/documents?current=1&size=10`
- `GET /api/xunzhi/v1/knowledge-documents/{documentId}`
- `DELETE /api/xunzhi/v1/knowledge-documents/{documentId}`

Only PDF uploads are accepted. The service checks the extension, MIME type, PDF
magic header and configurable maximum size (20 MiB by default), then generates a
UUID-based storage filename. `pypdf` extracts page text; whitespace is normalized
without discarding page numbers, and `APP_RAG_CHUNK_SIZE`/`APP_RAG_CHUNK_OVERLAP` control
deterministic page-aware chunks. Empty, encrypted and image-only PDFs are marked
`FAILED` with a safe error code and their temporary file is removed.

Migration `0003_knowledge_vector_tables` enables pgvector and creates
`knowledge_bases`, `knowledge_documents` and `knowledge_chunks`. The vector column
is fixed at 1536 dimensions for this migration; changing `APP_EMBEDDING_DIMENSIONS`
requires a new database migration. For local Docker verification:

```powershell
docker compose up -d postgres redis
uv run alembic upgrade head
uv run pytest -m integration
```

The default application uses `UnavailableEmbedding` so it starts without a real
provider. Production can inject `LangChainEmbeddingAdapter`; tests use the stable
`FakeEmbedding` and never call a paid embedding API.

## RAG chat retrieval

The existing chat endpoint accepts optional `knowledgeBaseId`, `topK` and
`similarityThreshold` fields. When a knowledge base is supplied, the backend
embeds the query, retrieves only `READY` chunks belonging to the authenticated
user and selected base, assembles a bounded reference context, and returns
citations in the SSE `complete` event. Without `knowledgeBaseId`, the legacy chat
request and SSE response are unchanged. Citations are persisted in
`message_citations` and are returned by chat history APIs.

Migration `0004_create_message_citations` adds the citation table with foreign
keys to messages, chunks and documents. `RAG_TOP_K`, `RAG_MAX_TOP_K`,
`RAG_SIMILARITY_THRESHOLD`, `RAG_MAX_CONTEXT_TOKENS` and
`RAG_MAX_CHUNK_TOKENS` are configurable through the corresponding `APP_`-
prefixed settings.

## Quality checks

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

Copy `.env.example` to `.env` for local configuration. The example contains only
local-development placeholders and must be replaced for any shared environment.
