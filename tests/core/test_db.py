import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import db
from app.core.db import connect_args, engine, session_scope, to_psycopg_url


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


async def test_app_engine_ends_idle_transactions():
    # The suite uses its own engine; this checks the timeout on the application engine.
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SHOW idle_in_transaction_session_timeout")) == "1min"
    finally:
        # No pooled connection may outlive the test event loop.
        await engine.dispose()


def test_zero_idle_timeout_sends_no_startup_option():
    # PgBouncer rejects an unknown startup option, so 0 must remove it.
    assert connect_args(0) == {}


@pytest.fixture
async def scoped_sessions(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    # session_scope() opens its sessions on the test connection. Its commit releases a savepoint,
    # and the test teardown rolls back the outer transaction and the temporary table.
    await db_session.execute(text("CREATE TEMPORARY TABLE scope_probe (name text NOT NULL)"))
    sessions = async_sessionmaker(db_session.bind, join_transaction_mode="create_savepoint", expire_on_commit=False)
    monkeypatch.setattr(db, "SessionLocal", sessions)


async def _probe_names(session: AsyncSession) -> list[str]:
    return list((await session.scalars(text("SELECT name FROM scope_probe ORDER BY name"))).all())


@pytest.mark.usefixtures("scoped_sessions")
async def test_session_scope_commits_on_success(db_session: AsyncSession):
    async with session_scope() as session:
        await session.execute(text("INSERT INTO scope_probe (name) VALUES ('kept')"))

    assert await _probe_names(db_session) == ["kept"]


@pytest.mark.usefixtures("scoped_sessions")
async def test_session_scope_rolls_back_on_error(db_session: AsyncSession):
    async def fail_after_insert() -> None:
        async with session_scope() as session:
            await session.execute(text("INSERT INTO scope_probe (name) VALUES ('discarded')"))
            raise RuntimeError("task failed")

    async with session_scope() as session:
        await session.execute(text("INSERT INTO scope_probe (name) VALUES ('kept')"))
    with pytest.raises(RuntimeError, match="task failed"):
        await fail_after_insert()

    assert await _probe_names(db_session) == ["kept"]
