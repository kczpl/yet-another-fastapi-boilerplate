# Yet another FastAPI boilerplate

A small feature-based FastAPI template for **Python 3.14** and **PostgreSQL 18**.
Celery/Redis and Pydantic AI/Bedrock are optional extras.

## This template

The `items` feature is an example. To start a project, follow
[the new project steps](.agents/references/new-project.md): name the project, remove the example
and the template files. The decisions behind the template are in [docs/review.md](docs/review.md).

## Architecture

```text
app/
├── main.py                  # FastAPI instance `api`, ASGI entry point `app`, probes /up and /ready
├── api/__init__.py          # Explicit router registration under /api/v1
├── models.py                # Explicit model registry for Alembic
├── core/                    # Settings, database, errors, logging, middleware
├── features/items/          # The example feature
│   ├── routes.py            # HTTP contracts and response envelopes
│   ├── dependencies.py      # Load/validate route resources
│   ├── schemas.py           # Pydantic request/response models
│   ├── models.py            # SQLAlchemy entities
│   ├── repository.py        # Queries and persistence; flush, never commit
│   ├── services/            # Use cases: create, list, update, delete, cleanup, summarize
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

To add a feature, follow [Add a feature](AGENTS.md#add-a-feature). Shared infrastructure
should not grow until there is a concrete second use case.

## Quickstart

Install [uv](https://docs.astral.sh/uv/), [just](https://just.systems/) and Docker.

```bash
just setup                          # all modules, .env and the ports of this checkout
just up                             # API + one migration job + PostgreSQL, in the background
just seed                           # demo data
just urls                           # the addresses of this checkout
```

`just up` builds the image, starts the stack in the background and waits until the API is
healthy. `just logs api` prints recent logs and stops; `just down` stops the stack.
Redis, workers and beat use the `workers` Compose profile (`COMPOSE_PROFILES=workers just up`).

Each checkout and each git worktree gets its own slot from `just setup`: a Compose project
name and ports base + N×10 (API 8000, PostgreSQL 5432, test PostgreSQL 5433, Redis 6379).
Parallel agents in worktrees therefore do not share containers or a test database. Read the
ports with `just urls`. Before you remove a worktree, run `just down -v` in it. Details:
[local development](.agents/references/local-development.md).

To run the API on the host:

```bash
docker compose up postgres -d --wait
just migrate
just app
```

`.env.example` uses localhost. Compose overrides database/broker hosts for
containers, so switching between host and Docker requires no edits. Keep JSON values in
single quotes: `just` removes the double quotes of an unquoted value.

## Optional workers and AI

| Installation | Includes |
|---|---|
| `uv sync --locked` | CRUD API, PostgreSQL, development tools |
| `uv sync --locked --extra workers` | Core + Celery/Redis worker and cron examples |
| `uv sync --locked --extra ai` | Workers + Pydantic AI/Bedrock and `/items/{id}/summarize` |

`just` recipes use the installed environment (`uv run --no-sync`), so select an
extra with `uv sync` first. `uv sync --locked` restores the core-only environment.
Type-checking every source module requires `uv sync --locked --all-extras`.

```bash
just workers                        # host workers; another terminal: just cron
docker compose --profile workers up --build
APP_EXTRA=ai docker compose --profile workers up --build
```

Tasks must be idempotent: late acknowledgements allow redelivery. Read
[the workers rule](.agents/rules/backend/background.md) and
[the workers reference](.agents/references/workers.md) before you change the queues, the time
limits or Redis. The AI example uses the standard AWS credential chain and the Bedrock Converse
API; see [the AI rule](.agents/rules/backend/ai-agents.md). Tests never call a live model.

## Migrations

Generate with `just makemigration "description"` and review upgrade/downgrade before
running `just migrate`. Tables and `alembic_version` live in `public`. Autogenerate inspects
only registered model tables, so **removing a model requires an explicit, reviewed
`drop_table` migration**. Details: [the database rule](.agents/rules/backend/database.md).

## Quality and tests

```bash
just lint                           # non-mutating Ruff format/lint checks
just ruff                           # format and autofix
just types                          # Pyright
just complexity                     # complexipy: cognitive complexity <= 10/function
just test                           # waits for PostgreSQL 18, applies migrations, tests
just ci                             # all local checks
just agents-check                   # agent guidance only (just test also runs it)
just audit                          # known vulnerabilities in uv.lock (network; not in ci)
```

CI checks the **core, workers and AI installations** on Python 3.14. It runs lint,
complexity, tests, a migration upgrade/check/downgrade/upgrade cycle, and builds
and imports runtime images without development dependencies. Pyright checks all
modules in the AI variant. Dependabot updates the actions and `uv.lock` each week.

Tests use migrated PostgreSQL schemas and rolled-back outer transactions with session
savepoints. `tests/architecture/` reads the source and enforces the layer rules: repositories
never commit, `app/core` and `app/utils` import no upper layer, only the `enqueue_*` helpers
publish tasks, models follow the database conventions, each route authenticates or is listed
as public, and logs carry no personal data. Details: [the testing rule](.agents/rules/backend/testing.md).

## Deployment

The image runs as a non-root user without uv and without development tools. It does not
migrate on startup: run the migration command once before you start the replicas. `/up` is the
liveness probe and `/ready` the readiness probe. The example routes are public: add
authentication for your product. Read [deployment](docs/deployment.md) for the probes, the
shutdown, the proxy settings and the security middleware.

Agent and coding guidance: [AGENTS.md](AGENTS.md) and [`.agents/`](.agents/README.md).
Every coding tool reads the same rules; the repository has no tool-specific copies.
