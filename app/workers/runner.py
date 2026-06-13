import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery.signals import worker_process_init, worker_process_shutdown

T = TypeVar("T")

_runner: asyncio.Runner | None = None


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    if _runner is None:
        raise RuntimeError("async runner not initialized — is this running inside a Celery worker?")
    return _runner.run(coro)


def run_service(service_cls: type, *args, **kwargs):
    from app.core.db.async_ import async_db_session

    async def _run():
        async with async_db_session() as db:
            return await service_cls(db).call(*args, **kwargs)

    return run_async(_run())


@worker_process_init.connect
def setup_async_runner(**kwargs):
    global _runner
    _runner = asyncio.Runner()

    # Forked children inherit the parent's connection pool with stale file
    # descriptors — dispose the Postgres engine and Redis client after fork.
    from app.core.db.async_ import async_engine, async_redis

    _runner.run(async_engine.dispose())
    _runner.run(async_redis.aclose())


@worker_process_shutdown.connect
def cleanup_async_runner(**kwargs):
    global _runner
    if _runner is None:
        return
    from app.core.db.async_ import async_engine, async_redis

    _runner.run(async_engine.dispose())
    _runner.run(async_redis.aclose())
    _runner.close()
    _runner = None
