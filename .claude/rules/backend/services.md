---
paths:
  - "app/**/*.py"
---

## Business Logic Layer — Services

Create a service class to encapsulate a single business use case, called directly from the router.
The service organizes logic into private step methods, with a main `call()` method that orchestrates them.

- Encapsulate reusable logic in `helpers.py` or repository functions, but each service represents one use case
- Keep service methods simple and minimal for easier testing and maintenance
- Prefer small denormalized methods over one big method that does everything
- Return a `dict` that gets validated by Pydantic at the API layer (via `response_model`)

IMPORTANT: role checks and auth happen at the API/dependency layer, never in services.

Services live inside each feature's `service/` directory:

```
features/items/service/
├── __init__.py
├── helpers.py      # reusable functions (e.g. serialize_item)
├── create.py       # CreateItemService (route-facing)
├── list.py         # ListItemsService (route-facing)
├── summarize.py    # SummarizeItemService (background task)
└── cleanup.py      # CleanupItemsService (background cron)
```

Base class:

```python
# app/services/base.py
from app.core.db import AsyncDb

class Service:
    def __init__(self, db: AsyncDb):
        self.db = db
```

Example — `call()` is a short orchestrator; steps are private methods:

```python
# app/features/items/service/create.py
class CreateItemService(Service):
    async def call(self, *, name: str, description: str | None = None) -> dict:
        item = await crud.create_item(self.db, name=name, description=description)
        await self.db.commit()
        return {"message": MESSAGES["created"], "data": serialize_item(item)}
```

### Passing domain objects to services

When a dependency has already loaded an entity (e.g. `valid_item_id` returns the `Item`), pass the **object** to the service rather than re-fetching by id. Pass the authenticated user object (once auth exists) instead of separate ids, and derive what you need from its preloaded relationships — never trigger a lazy load that issues an extra query.

## Background Tasks Layer

Tasks are the background equivalent of services — they encapsulate business logic that runs asynchronously via Celery. Same principles: single use case per task, private step methods, a `call()` orchestrator.

Architecture layers:

- `Service` base class (`app/services/base.py`) — stores `self.db: AsyncSession`
- Background task service classes (`features/<domain>/service/`) — same pattern as route-facing services
- Async runner (`app/workers/runner.py`) — one persistent `asyncio.Runner` per worker process + `run_service()` which opens a DB session, instantiates the service, and calls it
- Celery task functions (`app/workers/registry.py`) — thin wrappers that call `run_service(ServiceClass, *args, **kwargs)`
- Queue functions (`app/workers/queue.py`) — public API to enqueue tasks from application code

**Async runner lifecycle:** each Celery worker process (prefork) gets its own `asyncio.Runner` via the `worker_process_init` signal. The runner keeps one event loop alive across all tasks in that process, so async DB/Redis pools are reused. On `worker_process_shutdown` it disposes the engine and closes Redis.

Background task services live alongside route-facing services:

```python
# app/features/items/service/summarize.py — runs via summarize_item_task
class SummarizeItemService(Service):
    async def call(self, item_id: str) -> dict:
        item = await crud.get_item_by_id(self.db, UUID(item_id))
        if item is None or not item.description or item.summary is not None:
            return {"status": "skipped", "item_id": item_id}  # idempotent
        result = await summarize_text(item.description)
        await crud.set_item_summary(self.db, item, result.summary)
        return {"status": "summarized", "item_id": item_id}
```

```python
# app/workers/registry.py — thin Celery wrappers (service imported INSIDE the body)
@celery.task(name="tasks.summarize_item", queue=QUEUE_HEAVY, max_retries=1, time_limit=300)
def summarize_item_task(item_id: str) -> dict:
    from app.features.items.service.summarize import SummarizeItemService

    bind_context(item_id=item_id)
    return run_service(SummarizeItemService, item_id)
```

Background task services don't commit — `async_db_session` (inside `run_service`) commits on success and rolls back on exception. Route-facing services commit explicitly. See `background.md` for the full Celery handbook.

## Shared Services (`app/services/`)

Infrastructure shared across features:

- `base.py` — `Service` base class with the `AsyncDb` dependency (used by both route-facing services and background tasks)

Add cross-cutting infrastructure here (e.g. real-time pub/sub) only when more than one feature needs it.
