# Yet another FastAPI boilerplate

<p align="center">
  <em>Minimal, production-ready FastAPI + Celery template — feature-based architecture, async all the way down.</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white">
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white">
  <img alt="Celery" src="https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white">
  <img alt="pydantic-ai" src="https://img.shields.io/badge/pydantic--ai-Bedrock-E92063?logo=amazonaws&logoColor=white">
  <img alt="uv" src="https://img.shields.io/badge/uv-managed-DE5FE9?logo=uv&logoColor=white">
</p>

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
