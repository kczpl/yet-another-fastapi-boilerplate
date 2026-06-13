# CLAUDE.md

Minimal FastAPI + Celery boilerplate. Feature-based architecture, async SQLAlchemy (psycopg3), PostgreSQL, Redis, Celery, Pydantic v2, and pydantic-ai (AWS Bedrock) for AI agents.

## Quick Reference

- Package manager: `uv` · virtualenv `.venv` · run tooling with `uv run ...`
- Framework: FastAPI (async/await) · DB: PostgreSQL + SQLAlchemy 2.0 + psycopg3
- Background: Celery (Redis broker) · AI: pydantic-ai + Bedrock

## Rules

Detailed coding rules live in `.claude/rules/backend/` and auto-load when editing matching files. **Read the relevant rule before editing:**

| File | Covers |
|---|---|
| `core.md` | Python style, errors, middleware, `APIResponse`, logging, core modules |
| `routes.md` | API layer, dependencies-as-validation, pagination, response handling |
| `services.md` | Service classes (`call()` orchestrator), background task services |
| `database.md` | Models, conventions, UUIDv7, migrations, transaction ownership |
| `background.md` | Celery handbook — queues, retries, idempotency, fork safety |
| `integrations.md` | Sentry, Bedrock, adding external integrations |
| `ai-agents.md` | pydantic-ai + Bedrock conventions |
| `testing.md` | pytest-asyncio, factories, service/route/AI tests |

## Architecture

Request flow: `api/ → features/*/routes/ → features/*/service/ → repositories/`

```
app/
├── api/              # Router aggregation under /api/v1
├── core/             # config, db/, errors, exceptions, logger, security, responses, pagination, agents
├── features/         # Domain verticals: <domain>/{routes/, service/, schemas.py, agents/}
├── repositories/     # Data layer: <domain>/{models.py, crud.py, dependencies.py}
├── services/         # Shared Service base class
├── integrations/     # External services (sentry/, ...)
├── workers/          # Celery: celery.py, runner.py, registry.py, queue.py, queues.py
└── utils/            # Pure helpers (uuid, time)
```

- **`features/`** — each domain owns its routes, service classes (route-facing + background), and schemas
- **`repositories/`** — SQLAlchemy models, CRUD/query functions, and FastAPI access dependencies
- **`workers/`** — Celery tasks are thin wrappers; logic lives in service classes called via `run_service`

`items` is a complete example vertical slice (model → crud → service → route → AI task → tests). Copy it for a new feature, then delete it.

## Development

Run the whole stack in Docker (`docker compose up` / `just compose`): api, workers, cron, postgres, redis. API at `http://localhost:8000` (`/docs` in development).

Common commands (see `justfile`):

```bash
just app        # run API with reload (host)
just workers    # run Celery workers
just cron       # run Celery beat
just ruff       # format + lint
just types      # pyright
just migrate    # alembic upgrade head
just makemigration "create X table"
```

## Testing

Needs PostgreSQL (no DB mocks). Each test runs in a rolled-back transaction.

```bash
docker compose up postgres-test -d
uv run pytest          # or: just test
```

Mock third-party services (LLMs, external APIs) and Celery (`mock_celery` fixture). Test layout mirrors `app/`.

## Database

- PostgreSQL 18 (native `uuidv7()`). UUIDv7 primary keys via `app/utils/uuid.py`.
- No PostgreSQL ENUMs — use `String(n)` + `CheckConstraint`. Conventions in `app/core/db/base.py`.
- Always add a migration (`just makemigration`); never run migrations against production yourself.
