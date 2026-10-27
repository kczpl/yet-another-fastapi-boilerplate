import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import db
from app.core.db import session_scope, to_psycopg_url
from app.features.items import repository
from app.features.items.models import Item


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://app:app@db/app", "postgresql+psycopg://app:app@db/app"),
        ("postgresql+asyncpg://app:app@db/app", "postgresql+psycopg://app:app@db/app"),
        ("postgresql+psycopg://app:app@db/app", "postgresql+psycopg://app:app@db/app"),
    ],
)
def test_to_psycopg_url(url: str, expected: str):
    assert to_psycopg_url(url) == expected


@pytest.fixture
def scoped_sessions(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    # session_scope() opens its sessions on the test connection. Its commit releases a savepoint,
    # and the test teardown rolls back the outer transaction.
    sessions = async_sessionmaker(db_session.bind, join_transaction_mode="create_savepoint", expire_on_commit=False)
    monkeypatch.setattr(db, "SessionLocal", sessions)


@pytest.mark.usefixtures("scoped_sessions")
async def test_session_scope_commits_on_success(db_session: AsyncSession):
    async with session_scope() as session:
        item = await repository.create_item(session, name="Kept")

    assert await repository.get_item_by_id(db_session, item.id) is not None


@pytest.mark.usefixtures("scoped_sessions")
async def test_session_scope_rolls_back_on_error(db_session: AsyncSession):
    async def fail_after_insert() -> None:
        async with session_scope() as session:
            await repository.create_item(session, name="Discarded")
            raise RuntimeError("task failed")

    with pytest.raises(RuntimeError, match="task failed"):
        await fail_after_insert()

    assert await db_session.scalar(select(Item).where(Item.name == "Discarded")) is None
