# Agent instructions

Minimal feature-based FastAPI template. Python 3.14, PostgreSQL 18, async SQLAlchemy with
psycopg. Celery with Redis (`workers` extra) and Pydantic AI with Bedrock (`ai` extra) are
optional. UUIDv7 comes from the standard library: `from uuid import uuid7`.

## Load the rules

`AGENTS.md` and `.agents/` are the only agent guidance. The repository has no `CLAUDE.md`,
`.claude/` or `.codex/`. See [.agents/README.md](.agents/README.md) for the tool support.

1. At session start, read `.agents/rules/core.md` and `.agents/rules/git.md`.
2. Before you edit, run `just rules <file> ...` with each file that you will change, also new
   files. For a test, also give the file under test. Read each listed rule that is not in
   context.
3. Read a reference below only when its subject affects the change.
4. After compaction, run `just rules` again for the next edit.

The `paths:` frontmatter of each scoped rule is the only map from files to rules. `just rules`
without files prints the whole map.

## References

- Start a new project from this template: `.agents/references/new-project.md`.
- Run, call or test the app locally, also in a worktree: `.agents/references/local-development.md`.
- Authentication, roles or tenants: `.agents/references/auth-and-tenancy.md`.
- Worker time limits, the broker, Redis persistence or beat: `.agents/references/workers.md`.

## Layout

Each `app/features/<domain>/` owns `routes.py`, `dependencies.py`, `schemas.py`, `models.py`,
`repository.py` and the use cases in `services/`. AI agents live in the `agents/` directory of
their feature. `app/api/__init__.py` registers the routers. `app/models.py` registers the models
for Alembic. Do not create a second central tree of repositories or services.

Routes own HTTP and the response envelope. Services take an `AsyncSession`, call repository
functions and return entities or typed data. Repositories flush but never commit. A route-facing
service commits once per use case. A worker service relies on `session_scope()` in the runner.
Do not nest transaction owners. Commit before a slow call (LLM, HTTP, S3).

`app.main.api` is the FastAPI object for dependency overrides and OpenAPI. `app.main.app` is the
ASGI entry point. It wraps `api` with CORS, request logging and `SecurityMiddleware`.

## Add a feature

1. Create `app/features/<domain>/` with the files above. Add only the files that it uses.
2. Register the router in `app/api/__init__.py` and the models in `app/models.py`.
3. Add the error keys to `ERRORS` in `app/core/errors.py`.
4. Run `just makemigration "create <table> table"` and review the migration.
5. Give each route an auth dependency, or list it with the reason in `PUBLIC_ROUTES` of
   `tests/architecture/test_route_inventory.py`.
6. For a task, add it to `app/workers/registry.py` and an `enqueue_*` helper to
   `app/workers/enqueue.py`. Decide what finds its lost work (`background.md`).
7. Mirror the tests in `tests/features/<domain>/`. Put the factories in `tests/factories/`.

## Project gates

A gate checks one project convention: a ruff ban or a test in `tests/architecture/`. Run
`just gates` after each edit. It takes about 1 s and needs no database. Each finding names its
fix: fix the code. No comment switches a gate off. Turn a correction that comes back into a new
gate: read [gates](.agents/references/gates.md).

## Commands

- `just setup` runs first in each checkout and each worktree. It installs all modules and gives
  the checkout its own ports. Never assume port 8000; read `just urls`.
- `just up` starts the stack in the background and waits until it is healthy. `just logs api`
  prints recent logs and stops. `just seed` loads demo data. `just down` stops the stack.
- `uv sync --locked` installs only the core. `just app`, `just workers` and `just cron` run the
  installed environment on the host without a resync.
- `just ruff` formats and fixes. `just ci` runs `lint`, `gates`, `types`, `complexity` and `test`.
- `just test` starts PostgreSQL 18 in Docker. Tests apply the migrations and never mock the DB.
- `just makemigration "description"` and `just migrate` use the settings from env and `.env`.
- `just agents-check` checks the agent guidance only. `just test` also runs it.

## Safety

- Never run migrations against a production database.
- Never commit secrets or `.env`. Never log secrets, request bodies or LLM prompts.
- Keep `workers` and `ai` optional. The core API must import without them.
- Do not call live LLMs in tests or CI.
