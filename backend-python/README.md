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

## Authentication API

The versioned endpoints are:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

## Quality checks

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

Copy `.env.example` to `.env` for local configuration. The example contains only
local-development placeholders and must be replaced for any shared environment.
