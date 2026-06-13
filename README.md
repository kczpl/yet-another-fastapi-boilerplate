# Yet another FastAPI boilerplate

A minimal, lightweight FastAPI + Celery template following a feature-based architecture.

## Stack

- **FastAPI** (async) + **Pydantic v2**
- **PostgreSQL 18** + **SQLAlchemy 2.0** (async, psycopg3) + **Alembic**
- **Celery** (Redis broker) — workers + beat, with a persistent async runner
- **pydantic-ai** + **AWS Bedrock** for AI agents
- **structlog** + **Sentry**
- Tooling: **uv**, **ruff**, **pytest** (+ factory-boy), **just**

## Architecture

```
api/ → features/*/routes/ → features/*/service/ → repositories/
```

- `app/core/` — config, db, errors, logging, security, responses, pagination
- `app/features/<domain>/` — `routes/`, `service/`, `schemas.py`
- `app/repositories/<domain>/` — `models.py`, `crud.py`, `dependencies.py`
- `app/workers/` — Celery app, queues, task registry, enqueue helpers
- `app/core/agents.py` — shared pydantic-ai config (agents live in `features/*/agents/`)

Coding rules live in `.claude/rules/backend/`. The `items` feature is a complete example slice — copy it, then delete it.

## Quickstart

```bash
cp .env.example .env          # adjust as needed
uv sync                       # install deps (regenerates uv.lock on first run)

# everything in Docker (api + workers + cron + postgres + redis):
just compose

# or run pieces on the host:
docker compose up postgres redis -d
just migrate
just app                      # API at http://localhost:8000 (docs at /docs)
just workers                  # Celery workers
```

## Testing

```bash
docker compose up postgres-test -d
just test
```

## Common commands

```bash
just app | workers | cron | compose
just ruff | types | test | ci
just migrate
just makemigration "create X table"
```
