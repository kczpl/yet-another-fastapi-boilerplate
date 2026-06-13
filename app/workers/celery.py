import sys

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging as celery_setup_logging
from celery.signals import task_prerun

from app.core.config import celery_config, database_config
from app.core.logger import bind_context, clear_context, setup_logging
from app.integrations.sentry.client import init_sentry


@celery_setup_logging.connect
def _configure_logging(**kwargs):
    app_name = "cron" if "beat" in sys.argv else "workers"
    setup_logging(app=app_name)


init_sentry()


# Clears structlog contextvars between tasks on the same worker and binds task metadata.
@task_prerun.connect
def _bind_task_context(task_id=None, task=None, **_):
    clear_context()
    task_name = getattr(task, "name", None) if task is not None else None
    delivery_info = getattr(getattr(task, "request", None), "delivery_info", None) or {}
    queue = delivery_info.get("routing_key") or "unknown"

    ctx: dict[str, str] = {}
    if task_id:
        ctx["task_id"] = task_id
    if task_name:
        ctx["task_name"] = task_name
    if queue and queue != "unknown":
        ctx["queue"] = queue
    if ctx:
        bind_context(**ctx)


celery = Celery(
    "app",
    broker=database_config.REDIS_URL,
    task_cls="app.workers.base:BaseTask",
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Nothing reads task results (no AsyncResult / chords), so don't store them.
    task_ignore_result=True,
    task_acks_late=True,
    # A pool child killed mid-task (OOM/SIGKILL) would otherwise ACK and silently
    # lose the task despite acks_late. Reject requeues it — tasks must tolerate
    # re-delivery (see idempotency.py).
    task_reject_on_worker_lost=True,
    task_time_limit=celery_config.TASK_TIME_LIMIT,
    task_soft_time_limit=int(celery_config.TASK_TIME_LIMIT * 0.8),
    worker_prefetch_multiplier=1,
    worker_concurrency=celery_config.WORKER_CONCURRENCY,
    worker_max_tasks_per_child=celery_config.WORKER_MAX_TASKS_PER_CHILD,
    # Broker resilience: surface a dead peer in ~90s (vs the kernel's multi-minute
    # default), health-check every 30s, and retry forever.
    broker_transport_options={
        "socket_keepalive": True,
        "health_check_interval": 30,
    },
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_pool_limit=3,
    beat_schedule={
        # Example cron — replace with your own. Use crontab(...), not timedelta(...),
        # so Sentry Crons (monitor_beat_tasks=True) reads cron expressions.
        "example-cleanup": {
            "task": "tasks.example_cleanup",
            "schedule": crontab(hour=3, minute=0),  # 3 AM UTC daily
        },
        # Per-queue liveness probes — one per worker queue. A missed Sentry Cron
        # check-in means that queue's worker is down or wedged.
        "heartbeat-default": {"task": "tasks.heartbeat_default", "schedule": crontab(minute="*/5")},
        "heartbeat-heavy": {"task": "tasks.heartbeat_heavy", "schedule": crontab(minute="*/5")},
    },
)

celery.autodiscover_tasks(["app.workers"], related_name="registry")
