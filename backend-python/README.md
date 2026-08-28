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

## Quality checks

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

Copy `.env.example` to `.env` for local configuration. The example contains only
local-development placeholders and must be replaced for any shared environment.
