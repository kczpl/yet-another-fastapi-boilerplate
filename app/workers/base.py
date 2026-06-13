from celery import Task

from app.core.logger import log


class BaseTask(Task):
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        log.error(
            "celery_task_failed",
            task_id=task_id,
            task_name=self.name,
            exc_type=type(exc).__name__,
            exc_message=str(exc),
        )

    def on_success(self, retval, task_id, args, kwargs):
        log.info("celery_task_completed", task_id=task_id, task_name=self.name)
