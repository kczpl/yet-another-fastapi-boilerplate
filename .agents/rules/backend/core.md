# Backend conventions

- Python 3.14: standard-library `uuid.uuid7()`, modern type hints and named, typed results.
  Use PEP 695 generics (`class APIResponse[T]`, `def run_async[T]`). Ruff enforces them.
- Feature modules own their routes, dependencies, models, schemas, repository and services.
- Prefer functions for stateless work. A small service class groups one use case and its session.
- Keep short workflows inline. Extract a private helper only for a repeated or complex step.
- Do not add a generic repository, a dependency container or a base class without a use case.
- Use `uv` and the selected `.venv`. `just` runs the tools with `uv run --no-sync`.
- Put imports at the module top. Exceptions: optional integrations, and deferred imports in
  Celery task bodies (do not import services or network clients before the fork).
- In `async def`, never call blocking I/O or CPU-heavy work. Use an async client or
  `await asyncio.to_thread(...)`. Ruff `ASYNC` does not catch most of these calls.

## Complexity and types

Ruff checks the style and common mistakes. Pyright checks all modules with all extras installed.
Complexipy keeps the cognitive complexity at 10 or less per function in `app/`, `tests/` and
`alembic/`. Use early returns and direct logic. Do not hide complexity with suppressions or tiny
helpers. A low score alone does not make the code readable.

Use ORM entities, dataclasses or TypedDict for domain results. Pydantic validates HTTP input and
output and external data. Do not convert an entity to a response schema and back to a dict
before FastAPI validates the response again.

## Errors and responses

`ERRORS` in `app/core/errors.py` maps short literal keys to i18n keys. `APIException` rejects an
unregistered key, and the error-registry test finds misspelled `raise_*` calls. HTTP
dependencies use the `raise_*` helpers. Success responses use `APIResponse[T]` and `MESSAGES`;
routes own the envelope.

All errors use `{"error": "api.<domain>.<key>", "data": {...}}`, also the framework 404, 405 and
422 and the middleware 400, 403, 413 and 429. Build the envelope with `error_response()`. An
internal validation failure or an uncaught error is a 500 with a logged traceback, never a 422.

## Middleware

`setup_security_middleware()` in `app/core/security.py` builds the ASGI app. The order from the
outside is CORS, `LoggingMiddleware`, `SecurityMiddleware`, then FastAPI. The wrappers sit
outside FastAPI, so FastAPI's own 500 response also gets CORS, X-Request-ID and the security
headers. Write plain ASGI middleware. Do not use `BaseHTTPMiddleware`.

- `SecurityMiddleware` answers 403 to `BLOCKED_IPS` and 429 with `Retry-After` when a client IP
  goes above `RATE_LIMIT_PER_MINUTE`. It sets `SECURITY_HEADERS` on every HTTP response.
- The rate limit counts in process memory. N API processes allow N times the limit. Put strict,
  shared or per-route limits and WAF rules at the edge (load balancer or reverse proxy).
- `RequestSizeLimitMiddleware` sits inside FastAPI. It checks Content-Length and the bytes that
  the app reads, so a chunked body cannot pass the 10 MiB limit.
- The security headers have no CSP or COEP, because these block the CDN assets of `/docs`.

## Client IP and logging

The middleware uses the ASGI client address (`scope["client"]`). Uvicorn sets it from
X-Forwarded-For only for the proxies in `FORWARDED_ALLOW_IPS` (default: loopback). Behind a
proxy, set `FORWARDED_ALLOW_IPS` to the proxy addresses. If you do not, all clients share the
proxy IP and so they share one rate-limit count and one block decision. Do not parse
X-Forwarded-For in the app.

`LoggingMiddleware` clears and binds the log context for each request, propagates X-Request-ID
and logs one `http_request` event. It skips `/up`. Use static event names and put the values in
fields. Structlog writes JSON outside development. Do not log secrets, request bodies or prompts.

## Settings

Settings in `app/core/config.py` keep explicit values, also an empty CORS list and a zero pool
overflow. Configure the real origins and the pool size per process. Do not add placeholder
production domains.
