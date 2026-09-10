import sys
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging as celery_setup_logging
from celery.signals import task_prerun
from kombu import Queue

from app.core.config import celery_config
from app.core.logger import bind_context, clear_context, setup_logging
from app.integrations.sentry.client import init_sentry
from app.workers.queues import QUEUE_DEFAULT, QUEUE_HEAVY


@celery_setup_logging.connect
def _configure_logging(**kwargs):
    app_name = "cron" if "beat" in sys.argv else "workers"
    setup_logging(app=app_name)


init_sentry()


# Clears structlog contextvars between tasks on the same worker and binds task metadata.
@task_prerun.connect
def _bind_task_context(task_id: str | None = None, task: Any = None, **_):
    clear_context()
    delivery_info = getattr(task.request, "delivery_info", None) or {}
    context = {"task_id": task_id, "task_name": task.name, "queue": delivery_info.get("routing_key")}
    bind_context(**{key: value for key, value in context.items() if value})


celery = Celery(
    "app",
    broker=celery_config.REDIS_URL,
    task_cls="app.workers.base:BaseTask",
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_default_queue=QUEUE_DEFAULT,
    task_queues=(Queue(QUEUE_DEFAULT, durable=True), Queue(QUEUE_HEAVY, durable=True)),
    task_create_missing_queues=False,
    task_default_delivery_mode="persistent",
    timezone="UTC",
    enable_utc=True,
    # Nothing reads task results (no AsyncResult / chords), so don't store them.
    task_ignore_result=True,
    task_acks_late=True,
    # Business failures/timeouts are terminal unless a task explicitly retries.
    # Requeueing every failure would create unbounded poison-message loops.
    task_acks_on_failure_or_timeout=True,
    # A pool child killed mid-task (OOM/SIGKILL) would otherwise ACK and silently
    # lose the task despite acks_late. Reject requeues it — tasks must tolerate
    # re-delivery (see .claude/rules/backend/background.md → Retries and delivery).
    task_reject_on_worker_lost=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_time_limit=celery_config.TASK_TIME_LIMIT,
    task_soft_time_limit=int(celery_config.TASK_TIME_LIMIT * 0.8),
    worker_prefetch_multiplier=1,
    worker_concurrency=celery_config.WORKER_CONCURRENCY,
    worker_max_tasks_per_child=celery_config.WORKER_MAX_TASKS_PER_CHILD,
    # Producers retry within a finite budget; consumers keep reconnecting.
    task_publish_retry=True,
    task_publish_retry_policy={"max_retries": 3, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.5},
    broker_transport_options={
        "visibility_timeout": celery_config.BROKER_VISIBILITY_TIMEOUT,
        "max_retries": 3,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "socket_keepalive": True,
        "health_check_interval": 30,
    },
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_pool_limit=3,
    beat_sync_every=1,
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
