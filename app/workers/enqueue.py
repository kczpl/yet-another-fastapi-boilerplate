import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from uuid import UUID

from app.workers.base import BaseTask
from app.workers.celery import celery
from app.workers.registry import summarize_item_task

# Public API to enqueue tasks from application code. Feature code awaits these helpers
# after the commit. Never call task.delay() / task.apply_async() outside app/workers/.
# When you add a task, add a typed async enqueue_<task_name> helper here.

# A publish is a blocking broker call. These threads keep a hung broker away from the
# event loop and from the default thread pool. broker_pool_limit caps the connections.
_publisher = ThreadPoolExecutor(max_workers=celery.conf.broker_pool_limit, thread_name_prefix="celery-publish")


async def _delay(task: BaseTask, *args: object) -> None:
    # The copied context keeps the log and trace context of the caller in the publish.
    context = contextvars.copy_context()
    await asyncio.get_running_loop().run_in_executor(_publisher, partial(context.run, task.delay, *args))


async def enqueue_summarize_item(item_id: UUID) -> None:
    await _delay(summarize_item_task, str(item_id))
