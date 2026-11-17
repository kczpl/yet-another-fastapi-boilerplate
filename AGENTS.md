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

`tests/architecture/` enforces the layer rules. When one of its tests fails, fix the code. Do
not add an allowlist.

## Commands

- `uv sync --locked --all-extras` installs all modules. `uv sync --locked` installs only the core.
- `just app`, `just workers` and `just cron` run the selected environment without a resync.
- `just ruff` formats and fixes. `just ci` runs `lint`, `types`, `complexity` and `test`.
- `just test` starts PostgreSQL 18 in Docker. Tests apply the migrations and never mock the DB.
- `just makemigration "description"` and `just migrate` use the settings from env and `.env`.
- `just agents-check` checks the agent guidance only. `just test` also runs it.

## Safety

- Never run migrations against a production database.
- Never commit secrets or `.env`. Never log secrets, request bodies or LLM prompts.
- Keep `workers` and `ai` optional. The core API must import without them.
- Do not call live LLMs in tests or CI.
