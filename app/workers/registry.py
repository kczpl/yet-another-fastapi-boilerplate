from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

from app.core.logger import bind_context
from app.workers.base import BaseTask
from app.workers.celery import celery
from app.workers.queues import QUEUE_DEFAULT, QUEUE_HEAVY
from app.workers.runner import run_service

# Service classes are imported INSIDE task bodies, not at module level. This is the
# one sanctioned deferred-import location: feature services import app/workers/enqueue.py
# at the top, enqueue.py imports this module for the task objects, so a module-level
# service import here would close the features -> queue -> registry -> features cycle.

# Tasks without a beat task that finds their lost work. Each value gives the reason.
TASKS_WITHOUT_RECOVERY = {
    "tasks.summarize_item": "The client requests the summary again.",
}


def celery_task(*, recovered_by: str | None, **options: Any) -> Callable[[Callable[..., Any]], BaseTask]:
    # Late ACKs and one Redis broker can still lose a message. recovered_by names the beat task
    # that finds the lost work; a cron names itself. None needs an entry in TASKS_WITHOUT_RECOVERY.
    return cast(Callable[[Callable[..., Any]], BaseTask], celery.task(recovered_by=recovered_by, **options))


@celery_task(
    name="tasks.summarize_item",
    queue=QUEUE_HEAVY,
    recovered_by=None,
    max_retries=0,
    time_limit=300,
    soft_time_limit=240,
)
def summarize_item_task(item_id: str) -> dict:
    from app.features.items.services.summarize import SummarizeItemService

    bind_context(item_id=item_id)
    # JSON task arguments carry the id as str. Parse it here, at the task boundary.
    return run_service(SummarizeItemService, UUID(item_id))


@celery_task(
    name="tasks.example_cleanup",
    queue=QUEUE_DEFAULT,
    recovered_by="tasks.example_cleanup",
    max_retries=0,
    time_limit=300,
    soft_time_limit=240,
)
def example_cleanup_task() -> dict:
    # Idempotent cron — beat fires again next interval, so max_retries=0. Replace
    # the service with your own periodic job (see .agents/rules/backend/background.md).
    from app.features.items.services.cleanup import CleanupItemsService

    return run_service(CleanupItemsService)


# Liveness probes — one per worker queue. Bodies are pure on purpose (no DB/Redis)
# so the probe tests only "is this worker pulling and running tasks".
@celery_task(
    name="tasks.heartbeat_default",
    queue=QUEUE_DEFAULT,
    recovered_by="tasks.heartbeat_default",
    max_retries=0,
    time_limit=30,
    soft_time_limit=20,
)
def heartbeat_default_task() -> dict:
    return {"queue": QUEUE_DEFAULT}


@celery_task(
    name="tasks.heartbeat_heavy",
    queue=QUEUE_HEAVY,
    recovered_by="tasks.heartbeat_heavy",
    max_retries=0,
    time_limit=30,
    soft_time_limit=20,
)
def heartbeat_heavy_task() -> dict:
    return {"queue": QUEUE_HEAVY}
