import pytest

pytest.importorskip("celery")

from sqlalchemy import literal, select

from app.services.base import Service
from app.workers.runner import cleanup_async_runner, run_async, run_service, setup_async_runner


class EchoService(Service):
    async def call(self, value: int) -> int | None:
        return await self.db.scalar(select(literal(value)))


@pytest.fixture
def async_runner():
    # The same signal handlers that a worker process calls after fork and at shutdown.
    setup_async_runner()
    yield
    cleanup_async_runner()


@pytest.mark.usefixtures("async_runner")
def test_run_service_returns_the_service_result():
    assert run_service(EchoService, 42) == 42


def test_run_async_without_runner_fails():
    async def noop() -> None:
        return None

    with pytest.raises(RuntimeError, match="async runner not initialized"):
        run_async(noop())
