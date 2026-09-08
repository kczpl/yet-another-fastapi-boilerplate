import asyncio
import contextvars
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery.signals import worker_process_init, worker_process_shutdown

from app.core.db import engine, session_scope

T = TypeVar("T")

_runner: asyncio.Runner | None = None


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    if _runner is None:
        raise RuntimeError("async runner not initialized — is this running inside a Celery worker?")
    # Runner snapshots contextvars at its first run() (worker init, before any task) —
    # copy the current context per call so structlog bindings made in the task body
    # (task_id, item_id, ...) are visible to logs emitted inside the coroutine.
    return _runner.run(coro, context=contextvars.copy_context())


def run_service(service_cls: type, *args, **kwargs):
    # Opens a unit of work (commit on success / rollback on error), runs the
    # service on the worker's persistent event loop and returns its result.
    async def _run():
        async with session_scope() as db:
            return await service_cls(db).call(*args, **kwargs)

    return run_async(_run())


@worker_process_init.connect
def setup_async_runner(**kwargs):
    global _runner
    _runner = asyncio.Runner()
    # Forked children inherit the parent's connection pool with stale file
    # descriptors — dispose the Postgres engine after fork.
    _runner.run(engine.dispose())


@worker_process_shutdown.connect
def cleanup_async_runner(**kwargs):
    global _runner
    if _runner is None:
        return
    _runner.run(engine.dispose())
    _runner.close()
    _runner = None
