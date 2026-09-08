import os
from collections.abc import AsyncGenerator, Iterator
from unittest.mock import patch

# Must be set before importing app.core.config (engine is built at import time).
os.environ["DATABASE_URL"] = (
    f"postgresql+psycopg://app_test:app_test@localhost:{os.environ.get('POSTGRES_TEST_PORT', '5433')}/app_test"
)

import pytest
import pytest_asyncio
from celery.app.task import Task
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import app.repositories  # registers every model on Base.metadata
from app.core.db import Base, get_db
from app.main import app
from tests.factories.base import BaseFactory

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


def _factory_classes(cls: type[BaseFactory] = BaseFactory) -> Iterator[type[BaseFactory]]:
    # Every BaseFactory subclass imported by the test modules (collection happens
    # before fixtures run, so all factories a test can use are already loaded).
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _factory_classes(subclass)


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    # Each test runs inside a transaction that is rolled back afterwards, so tests
    # never see each other's writes.
    connection = await engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(
        connection,
        expire_on_commit=False,
        autoflush=False,
        # The session works on its own SAVEPOINT instead of the fixture's transaction:
        # commit() -> RELEASE SAVEPOINT, rollback() -> ROLLBACK TO SAVEPOINT. Without this
        # the default ("conditional_savepoint") degrades to "rollback_only" here, so a
        # rollback in the code under test would kill the outer transaction and wipe the
        # test's data. Note: rollback() also discards uncommitted setup rows — commit the
        # setup (`await db_session.commit()`) when the code under test rolls back.
        join_transaction_mode="create_savepoint",
    )()
    for factory_cls in _factory_classes():
        factory_cls._meta.sqlalchemy_session = session

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture(autouse=True)
def mock_celery():
    # No test ever reaches the broker: .delay() / .apply_async() on every task is a
    # mock. Celery calls it as apply_async(args, kwargs), so assert with
    # `mock_celery.assert_called_once_with((item_id,), {})`.
    with patch.object(Task, "apply_async") as mock_apply_async:
        yield mock_apply_async


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
