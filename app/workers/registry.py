from app.core.logger import bind_context
from app.workers.celery import celery
from app.workers.queues import QUEUE_DEFAULT, QUEUE_HEAVY
from app.workers.runner import run_service

# Service classes are imported INSIDE task bodies, not at module level. This is the
# one sanctioned deferred-import location: feature services import app/workers/queue.py
# at the top, queue.py imports this module for the task objects, so a module-level
# service import here would close the features -> queue -> registry -> features cycle.


@celery.task(name="tasks.summarize_item", queue=QUEUE_HEAVY, max_retries=1, time_limit=300)
def summarize_item_task(item_id: str) -> dict:
    from app.features.items.service.summarize import SummarizeItemService

    bind_context(item_id=item_id)
    return run_service(SummarizeItemService, item_id)


@celery.task(name="tasks.example_cleanup", queue=QUEUE_DEFAULT, time_limit=300, max_retries=0)
def example_cleanup_task() -> dict:
    # Idempotent cron — beat fires again next interval, so max_retries=0. Replace
    # the service with your own periodic job (see .claude/rules/backend/background.md).
    from app.features.items.service.cleanup import CleanupItemsService

    return run_service(CleanupItemsService)


# Liveness probes — one per worker queue. Bodies are pure on purpose (no DB/Redis)
# so the probe tests only "is this worker pulling and running tasks".
@celery.task(name="tasks.heartbeat_default", queue=QUEUE_DEFAULT, max_retries=0, time_limit=30)
def heartbeat_default_task() -> dict:
    return {"queue": QUEUE_DEFAULT}


@celery.task(name="tasks.heartbeat_heavy", queue=QUEUE_HEAVY, max_retries=0, time_limit=30)
def heartbeat_heavy_task() -> dict:
    return {"queue": QUEUE_HEAVY}
