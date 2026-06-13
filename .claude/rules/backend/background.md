---
paths:
  - "app/workers/**/*.py"
  - "app/features/**/service/**/*.py"
---

# Background Tasks & Celery

Operational handbook for Celery in this codebase. Architectural overview is in `services.md`.

## Core Principles

1. Tasks are thin wrappers - all logic in service classes. The `@celery.task` body binds context, calls `run_service(...)`, returns.
2. Every task must be safe to run twice - `task_acks_late=True` means a worker crash mid-task → broker re-delivers the same message.
3. Queue is explicit per task: `queue=QUEUE_X` in the decorator. No central `task_routes` dict.

## Queue Model

Two queues, split by **runtime characteristic** (not "importance"). Constants live in `app/workers/queues.py` — never hardcode queue strings.

| Queue | Constant | When | Examples |
|---|---|---|---|
| `default` | `QUEUE_DEFAULT` | <10s, user-blocking, fast crons | emails, notifications, dispatch tasks |
| `heavy` | `QUEUE_HEAVY` | >30s I/O bound | syncs, file/image processing, batch jobs, LLM/agent runs |

```python
from app.workers.queues import QUEUE_DEFAULT, QUEUE_HEAVY

@celery.task(name="tasks.summarize_item", queue=QUEUE_HEAVY, ...)
def summarize_item_task(...): ...
```

When in doubt → `default`. A fast task on `heavy` is fine; a slow task on `default` starves the fast lane. If LLM throughput ever needs its own throttle lane, add a dedicated `ai` queue — until then it lives on `heavy`.

## Retry Config

- Transient infrastructure errors (network, 5xx, throttle): `autoretry_for=(...)`, `max_retries=2-3`, `retry_backoff=True`, `retry_jitter=True`
- Business logic errors: never retry - fail, surface to Sentry
- Idempotent SQL crons: `max_retries=0`, beat fires again next interval

## Idempotency

Worker crash mid-task → re-delivery. The first execution might have partially mutated state; the second run must converge, not double-charge / double-send / double-write.

Patterns:
- **Cron jobs**: write a `processed_at` marker; the next run skips marked rows
- **Per-entity tasks**: check entity state at the top of the service, return early if already done (see `SummarizeItemService` — skips when `summary is not None`)
- **External side effects (email/webhooks)**: a per-enqueue `dedup_key` (`new_dedup_key()` from `app/workers/idempotency.py`) + a Redis delivery marker set only **after** the side effect succeeds, so broker re-delivery is a no-op while `autoretry_for` retries still fire
- **External APIs**: pass idempotency keys when supported

Don't dedup on the Celery `task_id` — retries reuse the same id.

## Database Session Lifecycle

`run_service()` wraps the call in `async_db_session()`, which auto-commits on success and rolls back on exception. Background services therefore do **not** call `commit()` themselves.

### Fork safety

`worker_process_init` in `runner.py` disposes the inherited Postgres engine and Redis client after fork. **Don't open DB/Redis/HTTP connections at module import time** — connections opened in the parent process are inherited as broken sockets by every child.

## Async / Sync

The worker uses prefork with a persistent `asyncio.Runner` per child process. `run_service` runs your coroutine on that loop.

- Prefer async-native I/O. For unavoidable sync SDKs, wrap with `asyncio.to_thread(...)`.
- For long polls, use `await asyncio.sleep(...)` — not `time.sleep` (which holds a thread-pool slot).
- From a sync context, use `run_async(coro)` from `app.workers.runner` — never `asyncio.run()`, the loop is already running.
- For LLM/HTTP batches: `asyncio.gather(..., return_exceptions=True)` + a `Semaphore(...)` to bound concurrency. One failure doesn't kill the batch.

### Sync task bodies

When a task is genuinely sync and has no DB, don't wrap with `run_service` for symmetry — just do the work and return.

## Logging

`task_prerun` (in `app/workers/celery.py`) auto-clears the previous task's contextvars and binds `task_id`, `task_name`, `queue`, and `app` for every task. Don't re-log them. For per-entity context, bind inside the task body:

```python
@celery.task(name="tasks.summarize_item", queue=QUEUE_HEAVY, ...)
def summarize_item_task(item_id: str) -> dict:
    from app.features.items.service.summarize import SummarizeItemService

    bind_context(item_id=item_id)
    return run_service(SummarizeItemService, item_id)
```

Never call `clear_context()` in a task body — `task_prerun` already cleared/bound; a body-level clear would wipe those bindings for the rest of the task's logs.

## Beat Schedule

Cron entries live in `beat_schedule={}` in `app/workers/celery.py`. Use `crontab(...)`, not `timedelta(...)` — `monitor_beat_tasks=True` (Sentry Crons) expects cron expressions. Pick a frequency where target runtime < 50% of the interval; schedule heavy work off-peak (`crontab(hour=3, minute=0)`).

Per-queue heartbeat tasks (`heartbeat_default`, `heartbeat_heavy`) are pure liveness probes — one Sentry Cron monitor per queue, so a down or wedged worker stops checking in and alerts.

## Enqueueing from Application Code

Use helpers in `app/workers/queue.py` — never call `task.delay()` / `task.apply_async()` directly from feature code. When adding a task, add a typed `enqueue_<task_name>` helper.

Feature services import queue helpers at the top of the file. To keep that cycle-free (`features → queue → registry`), `app/workers/registry.py` imports service classes lazily **inside** task bodies — the one sanctioned deferred-import location. Never import `app.features` at module level anywhere in `app/workers/`.

## Anti-patterns

- Hardcoded queue strings (`queue="default"`) — use the constants
- `try/except: pass` in a task body — swallows real bugs; use `autoretry_for=(SpecificError,)` instead
- Storing state on `self` with `bind=True` — tasks run on whatever worker picks them up, no continuity
- Task A enqueues B and awaits B's result — restructure as one task or chain via signatures
- Per-task DB pool tuning / custom session factory / manual transactions — stick to `run_service` + `async_db_session`
- Module-level network connections (boto3/redis/httpx client at import time) — breaks fork safety
