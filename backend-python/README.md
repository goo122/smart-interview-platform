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

## PostgreSQL/pgvector/Redis 集成测试门禁

集成测试位于 `tests/test_knowledge_integration.py`，覆盖 pgvector 写入与检索、事务和
唯一约束、用户/知识库隔离、PDF 分块、面试与报告持久化，以及 Redis TTL 和刷新会话。
它们不会调用 Chat 或 Embedding Provider；测试使用 Fake/Unavailable 实现。

前置条件：安装 Docker Desktop 并确保 Docker Engine 可访问。Windows、Linux 和 CI
均可使用同一个 Python 入口（入口只查找 PATH 中的 `docker`，找不到时使用 Docker
Desktop 的标准安装路径）：

```powershell
python backend-python/scripts/run_integration_tests.py
```

入口会校验 Compose、创建 `interviewplatform-integration` 专用 PostgreSQL 16/pgvector
和 Redis 容器，从空卷执行全部 Alembic 迁移，验证 `0009_resume_report_snapshot`、
`vector` 扩展和 1536 维向量列，然后连续运行两次 `pytest -m integration`，最后在
`finally` 中删除本轮容器、网络和数据卷。测试使用专用端口和密码，不读取
`backend-python/.env`，也不会触碰普通开发项目的资源。

普通测试默认排除 integration 标记：

```powershell
python -m pytest -m "not integration"
```

集成测试 fixture 要求 `RUN_INTEGRATION_TESTS=1`。一键入口显式设置该开关并注入
测试专用数据库/Redis 地址；如果变量缺失、服务不可达或迁移失败，测试会失败，
不会再用 `pytest.skip` 掩盖环境问题。直接手动运行时需同时提供该开关和两个
`KNOWLEDGE_TEST_*` 变量。

常见问题：Docker 不在 PATH 时入口会自动尝试 Docker Desktop 默认路径；端口被占用时
请先停止占用 25433/26380 的进程，或在专用 Compose 文件中调整端口。迁移失败时先
检查 PostgreSQL/Redis 健康状态和容器日志；不要连接开发数据库，也不要把真实
`.env`、密钥或连接字符串提交到 Git。

Copy `.env.example` to `.env` for local configuration. The example contains only
local-development placeholders and must be replaced for any shared environment.

## AI provider runtime configuration

The application selects ports at startup through `APP_AI_PROVIDER` and
`APP_EMBEDDING_PROVIDER`:

- `unavailable`: safe default; the process starts without external model calls;
- `fake`: deterministic development/test providers for chat, RAG embeddings,
  interview questions, scoring, follow-up questions and report narrative;
- `openai_compatible`: LangChain OpenAI-compatible adapters, requiring the
  corresponding API key, base URL and model settings.

`fake` is rejected in production. `openai_compatible` is rejected when any
required credential or endpoint setting is missing. `APP_AI_FAKE_MODE` accepts
`normal`, `follow_up` and `failure` for deterministic local workflow tests.
Embedding startup validation probes the selected provider and rejects a vector
dimension that does not match `APP_EMBEDDING_DIMENSIONS` (1536 by default).

Document embeddings use `APP_EMBEDDING_BATCH_SIZE=10` by default. The known
DashScope-compatible `text-embedding-v4` capability is limited to ten inputs
per provider request; configuring a larger value is rejected during Settings
validation instead of failing later during PDF import. The application and
LangChain SDK both receive the effective batch size, while query embeddings
remain single-text requests. Fake and unavailable providers have no additional
provider limit, but the same application batch setting is used for predictable
tests and local runs.

The root Compose file loads `backend-python/.env` with `env_file`; its explicit
PostgreSQL and Redis environment values still override those endpoints to the
Compose service names (`postgres` and `redis`). Never commit that `.env` file.

## Interview preparation

Interview preparation uses the authenticated user's ready resume knowledge base and
returns structured questions with traceable source citations. The API is available at:

- `POST /api/xunzhi/v1/interview/sessions`
- `GET /api/xunzhi/v1/interview/sessions?current=1&size=10`
- `GET /api/xunzhi/v1/interview/sessions/{sessionId}`
- `GET /api/xunzhi/v1/interview/sessions/{sessionId}/questions`
- `POST /api/xunzhi/v1/interview/sessions/{sessionId}/start`
- `POST /api/xunzhi/v1/interview/sessions/{sessionId}/cancel`

Migration `0005_create_interview_tables` creates sessions, questions, status events and
question citations. Preparation is orchestrated through the compiled
`InterviewPreparationWorkflow` LangGraph; LangGraph is a required runtime dependency
and the database remains the source of truth.

## Interview answers, evaluation and follow-up

After a session is started, the first `PRIMARY` turn is persisted as
`WAITING_ANSWER`. Authenticated clients use:

- `GET /api/xunzhi/v1/interview/sessions/{sessionId}/current-turn`
- `POST /api/xunzhi/v1/interview/sessions/{sessionId}/answers`
- `GET /api/xunzhi/v1/interview/sessions/{sessionId}/turns`
- `GET /api/xunzhi/v1/interview/sessions/{sessionId}/turns/{turnId}`

Answers are accepted with `turnId`, `answer` and an idempotent `requestId`. The
answer is stored before the asynchronous LangGraph evaluation workflow runs.
Scores are validated with `StructuredInterviewEvaluation`; deterministic
`FollowUpPolicy` enforces depth, score and per-session limits before a follow-up
generator can be called. Migration `0006_create_interview_turns_answers_evaluations`
creates turns, answers and evaluations. Interview state remains in PostgreSQL;
Redis is available for future worker locks but is not the source of truth.

## Final interview reports

Only sessions with status `COMPLETED` can produce a report. The report is an
immutable replay snapshot of completed turns, answers, evaluations and bounded
RAG citations. Generation is idempotent per session and uses a database row lock
to prevent concurrent duplicate generation. If a narrative provider is not
configured or returns invalid output, deterministic rule-based narrative is used
and the report is still marked `READY` with `generatedBy: RULES`.

Endpoints (all require the authenticated user's Bearer access token):

- `POST /api/xunzhi/v1/interview/sessions/{sessionId}/report`
- `GET /api/xunzhi/v1/interview/sessions/{sessionId}/report`
- `GET /api/xunzhi/v1/interview/reports?current=1&size=10`
- `GET /api/xunzhi/v1/interview/reports/{reportId}`

Migration `0007_create_interview_reports` creates `interview_reports` and
`interview_report_items`, including score bounds, the one-report-per-session
constraint and ordered replay-item uniqueness. To apply or inspect it:

```powershell
uv run alembic upgrade head
uv run alembic heads
uv run alembic check
uv run alembic upgrade head --sql > migration.sql
```

The deterministic defaults are configurable with `APP_REPORT_*` settings in
`.env.example`; no real model key or secret is required for local startup or
tests.
