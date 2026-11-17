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

Copy `features/items/` to start a feature, then register its router in `app/api/`
and model in `app/models.py`. Add a migration and tests alongside the feature.
Shared infrastructure should not grow until there is a concrete second use case.

## Quickstart

Install [uv](https://docs.astral.sh/uv/), [just](https://just.systems/) and Docker.

```bash
just setup                          # all modules, .env and the ports of this checkout
just up                             # API + one migration job + PostgreSQL, in the background
just seed                           # three demo items
just urls                           # the addresses of this checkout
```

`just up` builds the image, starts the stack in the background and waits until the API is
healthy. `just logs api` prints recent logs and stops; `just down` stops the stack.
The `postgres-test` service only starts when explicitly requested. Redis, workers
and beat use the `workers` Compose profile (`COMPOSE_PROFILES=workers just up`). API
startup waits for migrations; worker startup waits for both migrations and Redis.

Each checkout and each git worktree gets its own slot from `just setup`: a Compose project
name and ports base + N×10 (API 8000, PostgreSQL 5432, test PostgreSQL 5433, Redis 6379).
Parallel agents in worktrees therefore do not share containers or a test database. A slot
also skips ports that another project on the machine holds. Read the ports with `just urls`.
Before you remove a worktree, run `just down -v` in it.

To run the API on the host:

```bash
docker compose up postgres -d --wait
just migrate
just app
```

`.env.example` uses localhost. Compose overrides database/broker hosts for
containers, so switching between host and Docker requires no edits. `just setup` writes the
slot ports into the localhost URLs of `.env`. Keep JSON values in single quotes: `just`
removes the double quotes of an unquoted value.

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
credentials. `BEDROCK_MODEL` defaults to `eu.anthropic.claude-sonnet-5-5`. Set an inference
profile enabled in your account. The example uses the Bedrock Converse API, so check that the
model supports Converse. `AI_REQUEST_TIMEOUT` (default 60 seconds) is the deadline for one
model request. Tests never call a live model.

Workers consume the declared `default` and `heavy` queues; unrouted tasks go to
`default`, and misspelled queue names fail before publishing. Late acknowledgements
and requeueing on worker loss allow redelivery: tasks must be idempotent. Ordinary
failures/timeouts are acknowledged; add bounded retries for specific transient
exceptions in each task. `max_retries` alone does not enable retries.

Compose runs Redis 8 with a volume, AOF, `appendfsync always` and `noeviction`.
`BROKER_VISIBILITY_TIMEOUT` (default 3600 s) must exceed the longest task's hard limit
plus any ETA. Keep one beat instance per deployment. Workers get 11 minutes to finish on
SIGTERM (`WORKER_STOP_GRACE_PERIOD`). Restart workers after code changes
(`docker compose restart workers`); API hot reload remains enabled. Read
[the workers reference](.agents/references/workers.md) before you change these settings or
upgrade an existing Redis volume.

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
just setup                          # all extras, .env and the ports of this checkout
just lint                           # non-mutating Ruff format/lint checks
just ruff                           # format and autofix
just types                          # Pyright
just complexity                     # complexipy: cognitive complexity <= 10/function
just test                           # waits for PostgreSQL 18, applies migrations, tests
just ci                             # all local checks
just agents-check                   # agent guidance only (just test also runs it)
just audit                          # known vulnerabilities in uv.lock (network; not in ci)
just makemigration "create widgets table"
```

CI checks **core, workers and AI installations** on Python 3.14. It runs lint,
complexity, tests, a migration upgrade/check/downgrade/upgrade cycle, and builds
and imports runtime images without development dependencies. Pyright checks all
modules in the AI variant.

Tests use migrated PostgreSQL schemas and rolled-back outer transactions with
session savepoints. Tests and async fixtures share one event loop. Factories
supply test data; external model calls and Celery publishing are mocked.

`tests/architecture/` reads the source and the model metadata and enforces the layer
rules: repositories never commit, `app/core` and `app/utils` import no upper layer, only
the `enqueue_*` helpers publish tasks, models follow the database conventions, each
route authenticates or is listed as public, and logs carry no personal data.
`tests/migrations/test_heads.py` keeps one Alembic head. Pyright also reports a
`# type: ignore` that is not necessary.

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
`/up` checks process liveness. It does not check the database or the broker.

Small ASGI middleware classes in `app/core/security.py` replace a security package:

| Setting or limit | Behavior |
|---|---|
| Request body: 10 MiB | Checks `Content-Length` and the bytes read, also for chunked bodies. 400 or 413. |
| `RATE_LIMIT_PER_MINUTE` (default 1000, `0` disables) | Fixed window per client IP and API process. 429 with `Retry-After`. `/up` is exempt. |
| `BLOCKED_IPS` (JSON list of addresses or CIDRs) | 403 for HTTP, close code 1008 for WebSocket. |
| Security headers | HSTS, `nosniff`, `X-Frame-Options: DENY`, referrer, cross-origin and permissions policies on each response. |
| Request log | One `http_request` event with the status, the duration and `X-Request-ID`. |

The rate limit lives in process memory. N API processes allow N times the limit, and a
restart clears the counts. Put strict, shared or per-route limits, WAF rules and ingress
body/time limits at the reverse proxy or load balancer. The headers have no CSP, because a
CSP blocks the CDN assets of `/docs`. Add one when the API serves no HTML.

The middleware reads the client IP from the ASGI scope. Uvicorn takes it from
`X-Forwarded-For` only for proxies in `FORWARDED_ALLOW_IPS` (default: loopback). Behind a
proxy, set `FORWARDED_ALLOW_IPS` to the proxy addresses or network. If you do not, all clients
share the proxy IP: one rate-limit count and one block decision for everybody. Never set
`FORWARDED_ALLOW_IPS=*` when clients can reach Uvicorn directly, because they can then forge
their IP.

The AI example skips completed summaries on sequential redelivery. It does not
promise exactly-once model calls under concurrent tasks or a crash between a model
response and commit. Add locking/idempotency or a transactional outbox when a real
workflow needs those guarantees.

Detailed review and implementation decisions: [docs/review.md](docs/review.md).
Agent and coding guidance: [AGENTS.md](AGENTS.md) and [`.agents/`](.agents/README.md).
Every coding tool reads the same rules; the repository has no tool-specific copies.
