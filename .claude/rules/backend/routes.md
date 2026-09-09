---
paths:
  - "app/features/**/routes.py"
  - "app/features/**/ai_routes.py"
  - "app/features/**/dependencies.py"
  - "app/features/**/schemas.py"
  - "app/api/**/*.py"
---

# HTTP layer

Routes live beside their feature. Use explicit full paths without trailing slashes; apply
`/api/v1` once in `app/api/__init__.py`. Declare response_model and status_code.

Use async routes for async I/O. Sync-only operations such as Celery `.delay()` belong in a
sync route (FastAPI's thread pool) or an explicit thread-pool call, never directly in async code.

Pydantic validates request shape. Feature `dependencies.py` loads resources and checks HTTP
identity/access. Reuse annotated dependencies such as `ValidItem`; pass the loaded object to
services instead of fetching it again. Keep database queries in `repository.py`.

Routes construct services with the injected `AsyncDb` session. Services themselves take a plain
`AsyncSession`, so they work in HTTP, workers and direct tests without FastAPI annotations.
Return domain objects under `{"data": result}` with optional `MESSAGES` keys. Response schemas
use `from_attributes=True` for ORM entities. Load required relationships before serialization.

Pagination defaults: page=1, page_size=10, max page_size=100. Return items, page, page_size,
total_count, total_pages. Preserve totals on empty out-of-range pages. Use a deterministic order
with a unique tie-breaker. A count query is clearer than a window count that disappears on empty pages.

The AI endpoint is registered only when its extra is installed. Keep core CRUD independent of
optional worker/model imports. CORS is configured explicitly via CORS_ORIGINS.
