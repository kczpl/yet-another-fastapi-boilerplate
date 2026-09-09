# Project conventions

Minimal feature-based FastAPI template. Python 3.14, PostgreSQL 18, async
SQLAlchemy/psycopg. Celery/Redis (`workers`) and Pydantic AI/Bedrock (`ai`) are
optional extras. UUIDv7 comes from the standard library: `from uuid import uuid7`.

## Layout

Each `app/features/<domain>/` owns `routes.py`, `dependencies.py`, `schemas.py`,
`models.py`, `repository.py` and use cases in `services/`. Agents live beside
their feature. `app/api/__init__.py` registers routers; `app/models.py` registers
models for Alembic. Do not create a second central domain repository tree.

Routes own HTTP and response envelopes. Services accept `AsyncSession`, return
entities/typed data, and call repository functions. Repositories flush but never
commit. Route-facing services commit once per use case; worker services rely on
`session_scope()` in the runner. Avoid nested transaction owners.

## Development

- Run `uv sync --locked --all-extras` for work across all modules; core only: `uv sync --locked`.
- `just app`, `just workers`, `just cron` use the selected environment without resyncing.
- `just lint`, `just types`, `just complexity`, `just test`; `just ci` runs all four.
- `just ruff` formats/fixes. Cognitive complexity must remain <= 10 per function.
- `just migrate` and `just makemigration "description"` use the app's env/.env settings.
- Tests use actual PostgreSQL 18 migrations and savepoint isolation, never DB mocks.
- `app.main.api` is the FastAPI object for dependencies/OpenAPI; `app.main.app` is
  the ASGI entry point wrapped for CORS, security headers and request logging on 500s too.

## Rules

Read the relevant `.claude/rules/backend/` document before editing its area:
`core.md`, `routes.md`, `services.md`, `database.md`, `background.md`,
`integrations.md`, `ai-agents.md`, `testing.md`.

Keep code small without fragmenting simple workflows into one-line helpers.
Add abstractions only for existing repetition. Never run migrations against a
production database yourself.
