---
paths:
  - "app/**/*.py"
---

# Core conventions

- Python 3.14; standard-library `uuid.uuid7()`, modern type hints, named typed results.
- Feature modules own their routes, dependencies, models, schemas, repository and services.
- Prefer functions for stateless work. A small service class groups one use case and its DB session.
- Keep short workflows inline. Extract private helpers only for meaningful repeated/complex steps.
- Use `uv` and the selected `.venv`; `just` runs tools with `uv run --no-sync`.
- Do not introduce a generic repository, dependency container or base hierarchy without a use case.
- Imports normally belong at module top. Explicit exceptions: optional integrations and deferred
  imports in Celery task bodies (avoid importing services/network clients before fork).

## Complexity and types

Ruff checks style and common mistakes; Pyright checks all modules with all extras installed.
Complexipy enforces cognitive complexity <= 10 per function across app, tests and migrations.
Prefer early returns and direct logic; do not hide complexity with suppressions or tiny indirection.
A low score alone does not imply readable architecture.

Use ORM entities, dataclasses or TypedDict for domain results. Pydantic handles HTTP input/output
and external data validation. Do not convert an entity to a response schema and back to a dict
before FastAPI validates the response again.

## Errors and responses

`ERRORS` maps short literal keys to i18n keys. `APIException` checks registration and the static
error-registry test catches misspelled `raise_*` calls. HTTP dependencies use the raise helpers.
Success responses use `APIResponse[T]` and `MESSAGES`; routes own the envelope.
Errors use `{"error": "api.<domain>.<key>", "data": {...}}`, including framework 404/405/422.
Internal validation failures and uncaught errors are 500s with a logged traceback, never client 422s.

## Middleware and logging

The exported ASGI app wraps FastAPI with CORS → security headers → request logging. These wrappers
also process FastAPI's unhandled 500 responses. Request-size checking sits inside FastAPI and
checks Content-Length plus actual consumed bytes (10 MiB). Do not use BaseHTTPMiddleware.

Logging binds/clears context per request, propagates X-Request-ID, and skips `/up`. Trust the
ASGI client address resolved by Uvicorn's configured trusted proxies; never parse arbitrary
X-Forwarded-For as authoritative. Structlog emits JSON outside development. Do not log secrets,
request bodies or LLM prompts. Rate limiting and ingress time/body limits belong at the edge.

Settings keep explicit values, including empty CORS lists and zero pool overflow. Configure
real origins and per-process pool sizes; do not insert placeholder production domains.
