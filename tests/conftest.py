import importlib
import os
import pkgutil
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

# Must be set before importing app.core.config (engine is built at import time).
os.environ["DATABASE_URL"] = (
    f"postgresql+psycopg://app_test:app_test@localhost:{os.environ.get('POSTGRES_TEST_PORT', '5433')}/app_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import tests.factories as _factories_pkg
from app.core.db import Base, _get_async_db
from app.main import app
from tests.factories.base import BaseFactory

# Auto-discover every factory module so all BaseFactory subclasses exist.
for _importer, _modname, _ispkg in pkgutil.walk_packages(_factories_pkg.__path__, prefix="tests.factories."):
    importlib.import_module(_modname)

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    # Each test runs inside a transaction that is rolled back afterwards, so tests
    # never see each other's writes.
    connection = await engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False, autoflush=False)()

    def _all_factory_subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from _all_factory_subclasses(sub)

    for factory_cls in _all_factory_subclasses(BaseFactory):
        factory_cls._meta.sqlalchemy_session = session

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
def mock_celery():
    # Never enqueue real Celery tasks in tests. Patch enqueue helpers' task objects.
    with patch("app.workers.registry.summarize_item_task.delay") as mock_delay:
        mock_delay.return_value = MagicMock(id="test-task-id")
        yield mock_delay


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_celery) -> AsyncGenerator[AsyncClient]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_async_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
