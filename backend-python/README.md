# AI Interview Backend

Minimal FastAPI foundation for the intelligent mock interview platform.

## Local development

```powershell
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Quality checks

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

Copy `.env.example` to `.env` for local configuration. The example contains only
local-development placeholders and must be replaced for any shared environment.

