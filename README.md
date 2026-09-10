# Yet another FastAPI boilerplate

A small feature-based FastAPI template for **Python 3.14** and **PostgreSQL 18**.
Celery/Redis and Pydantic AI/Bedrock are optional examples.

## Architecture

```text
app/
├── main.py                  # FastAPI instance `api`, wrapped ASGI entry point `app`
├── api/__init__.py          # Explicit router registration under /api/v1
├── models.py                # Explicit model registry for Alembic
├── core/                    # Settings, database, errors, logging, middleware
├── features/items/
│   ├── routes.py            # HTTP contracts and response envelopes
│   ├── dependencies.py      # Load/validate route resources
│   ├── schemas.py           # Pydantic request/response models
│   ├── models.py            # SQLAlchemy entities
│   ├── repository.py        # Queries and persistence; flush, never commit
│   ├── services/            # Use cases: create, list, cleanup, summarize
│   ├── ai_routes.py         # Enabled by installing the ai extra
│   └── agents/              # Optional AI wrapper
├── services/base.py         # Shared AsyncSession constructor
├── workers/                 # Optional Celery infrastructure and task registry
├── integrations/sentry/     # Optional DSN; no telemetry in development
└── utils/time.py
```

Request flow: **routes → services → repository**. Resource dependencies can load
an entity directly from the repository and return a 404 before calling a service.
Services accept `AsyncSession` and return entities or typed data. Routes own the
API envelope, and Pydantic validates/serializes at the HTTP boundary.

Repositories only flush. A route-facing use case commits explicitly; worker use
cases commit through `session_scope()`. Compose several writes inside one service
before committing. Don't call a committing service from another transaction owner.
No generic repository, abstract service hierarchy, or mandatory helper per step.

Copy `features/items/` to start a feature, then register its router in `app/api/`
and model in `app/models.py`. Add a migration and tests alongside the feature.
Shared infrastructure should not grow until there is a concrete second use case.

## Quickstart

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
cp .env.example .env
uv sync --locked                    # core + development tools; Python from .python-version
just compose                        # API + one migration job + PostgreSQL
```

API: http://localhost:8000 · docs: `/docs` · liveness: `/up`.
The `postgres-test` service only starts when explicitly requested. Redis, workers
and beat use the `workers` Compose profile. API startup waits for migrations;
worker startup waits for both migrations and Redis.

To run the API on the host:

```bash
docker compose up postgres -d --wait
just migrate
just app
```

`.env.example` uses localhost. Compose overrides database/broker hosts for
containers, so switching between host and Docker requires no edits. If you change
host port mappings, update the corresponding URLs in `.env` as well.

## Optional workers and AI

| Installation | Includes |
|---|---|
| `uv sync --locked` | CRUD API, PostgreSQL, development tools |
| `uv sync --locked --extra workers` | Core + Celery/Redis worker and cron examples |
| `uv sync --locked --extra ai` | Workers + Pydantic AI/Bedrock and `/items/{id}/summarize` |

`just` recipes use the installed environment (`uv run --no-sync`), so select an
extra with `uv sync` first. `uv sync --locked` restores the core-only environment.
Type-checking every source module requires `uv sync --locked --all-extras`.

Host workers:

```bash
uv sync --locked --extra workers     # or --extra ai
docker compose up postgres redis -d --wait
just migrate
just workers                        # another terminal: just cron
```

Docker workers:

```bash
docker compose --profile workers up --build
# API + workers with the AI example:
APP_EXTRA=ai docker compose --profile workers up --build
```

AWS credentials use the standard SDK chain: exported `AWS_PROFILE`, standard AWS
credential variables (including session tokens), or an IAM role. For Docker, pass
credentials/profile access explicitly using your deployment's mechanism. Model
clients are created on first use, after worker fork; API import needs no AWS
credentials. Configure `BEDROCK_MODEL` for an inference profile enabled in your
account. Tests never call a live model.

Workers consume the declared `default` and `heavy` queues; unrouted tasks go to
`default`, and misspelled queue names fail before publishing. Late acknowledgements
and requeueing on worker loss allow redelivery: tasks must be idempotent. Ordinary
failures/timeouts are acknowledged; add bounded retries for specific transient
exceptions in each task. `max_retries` alone does not enable retries.

Compose persists Redis to a volume with AOF, `appendfsync always` and `noeviction`.
Fsync before acknowledging writes trades throughput for stronger persistence.
This is a single broker, with no high availability or guarantee against disk/node
loss. Persistent messages do not provide exactly-once execution. See
[Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).
When upgrading an **existing RDB-only Redis volume**, back it up and enable AOF
online (`CONFIG SET appendonly yes`); wait for successful AOF rewrite before
restarting with this Compose configuration. Restarting with AOF enabled without
first converting the existing data can lose it.

`BROKER_VISIBILITY_TIMEOUT` defaults to 3600 seconds and must exceed the longest
task's hard limit plus any ETA/countdown. Startup validates it against the global
`TASK_TIME_LIMIT` (600 seconds); check task-specific overrides yourself. Whole-worker
loss can delay redelivery until this timeout. Avoid long ETA reservations in Redis.
Keep one beat instance per deployment; Compose persists its schedule in
`celery_beat_data`. Beat is not a durable job ledger or a missed-run catch-up service.
Workers receive SIGTERM directly and get 11 minutes to finish; adjust
`WORKER_STOP_GRACE_PERIOD` when increasing task limits. Restart workers after code
changes (`docker compose restart workers`); API hot reload remains enabled.

## Migrations

Generate with `just makemigration "description"` and review upgrade/downgrade before
running `just migrate`. Filenames follow
`YYYY_MM_DD_HHMM-<revision>_<slug>.py`, using UTC; Alembic orders by revision links,
not by filename. Ruff hooks use the active Python environment with dev tools installed.

Application tables and `alembic_version` live in `public`, independently of the
connection's default schema. Autogenerate inspects only registered model tables
in `public`, so unrelated tables are not proposed for deletion. Consequently,
**removing a model requires an explicit, reviewed `drop_table` migration**.
Autogenerate can still propose destructive changes inside managed tables. Constraint
and index names come from shared metadata; composite names include all columns.

## Quality and tests

```bash
uv sync --locked --all-extras
just lint                           # non-mutating Ruff format/lint checks
just ruff                           # format and autofix
just types                          # Pyright
just complexity                     # complexipy: cognitive complexity <= 10/function
just test                           # waits for PostgreSQL 18, applies migrations, tests
just ci                             # all local checks
just makemigration "create widgets table"
```

CI checks **core, workers and AI installations** on Python 3.14. It runs lint,
complexity, tests, a migration upgrade/check/downgrade/upgrade cycle, and builds
and imports runtime images without development dependencies. Pyright checks all
modules in the AI variant.

Tests use migrated PostgreSQL schemas and rolled-back outer transactions with
session savepoints. Tests and async fixtures share one event loop. Factories
supply test data; external model calls and Celery publishing are mocked.

Ruff also checks security patterns (`S`), timezone mistakes (`DTZ`), debugger calls
(`T10`), pytest conventions (`PT`), and redundant code (`PIE`, `RET`). Exceptions
are narrow: assertions are allowed in tests, and FastAPI dependency markers are
recognized by `B008`. These checks complement Pyright and complexipy.

Complexity is a guardrail, not a readability score: prefer early returns and
clear names, and extract helpers only when they clarify meaningful steps.

## Deployment boundaries

The Docker image runs as a non-root user and does not run migrations in its
entrypoint. Compose supplies a separate migration job. In another deployment,
run the same migration command once before starting replicas.

The example CRUD routes are public. Add authentication for your product, with
HTTP identity/access checks in dependencies and business invariants in services.
CORS defaults to no origins; list deployed frontend origins explicitly.
Docs and OpenAPI default to disabled outside development (`SHOW_DOCS` overrides).

The app limits consumed request bodies to 10 MiB, including chunked requests.
Set ingress body/time limits and rate limiting at your reverse proxy. Uvicorn
should only trust forwarded headers from known proxy addresses. `/up` checks
process liveness; it deliberately does not assert database or broker readiness.

The AI example skips completed summaries on sequential redelivery. It does not
promise exactly-once model calls under concurrent tasks or a crash between a model
response and commit. Add locking/idempotency or a transactional outbox when a real
workflow needs those guarantees.

Detailed review and implementation decisions: [docs/review.md](docs/review.md).
Coding guidance: [CLAUDE.md](CLAUDE.md) and `.claude/rules/backend/`.
