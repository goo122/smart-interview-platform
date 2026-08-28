# Project Instructions

## Architecture

- Backend uses FastAPI, Pydantic v2 and SQLAlchemy 2.
- Business logic must not be placed in API routers.
- Routers call services, and services depend on repository abstractions.
- PostgreSQL is the source of truth.
- Redis is used only for cache, locks, rate limits and temporary state.
- LangGraph orchestrates workflows but is not the source of truth.
- AI outputs must use Pydantic structured models.
- RAG requests must filter by user_id and knowledge_base_id.

## Code Quality

- Every new service requires unit tests.
- Every new endpoint requires API tests.
- Use async interfaces for network and database operations.
- Do not hard-code secrets.
- Do not silently catch exceptions.
- Run Ruff, mypy and pytest before completing a task.
- Do not modify unrelated files.

## Workflow

- Inspect relevant files before editing.
- State assumptions before implementing ambiguous behavior.
- Implement one vertical slice at a time.
- Report changed files, tests and remaining risks.

