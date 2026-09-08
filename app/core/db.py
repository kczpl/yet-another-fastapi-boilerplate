from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import database_config

# PostgreSQL naming convention for constraints and indexes — applied by SQLAlchemy
# MetaData and by Alembic ops (env.py passes target_metadata). The names it
# produces are listed in .claude/rules/backend/database.md.
NAMING_CONVENTION = {
    "ix": "%(table_name)s_%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def to_psycopg_url(url: str) -> str:
    # Normalize any common Postgres URL flavor onto the async psycopg3 driver.
    for prefix in ("postgresql://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql+psycopg://", 1)
    return url


engine = create_async_engine(
    to_psycopg_url(database_config.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=database_config.POOL_SIZE,
    max_overflow=database_config.POOL_MAX_OVERFLOW,
    pool_timeout=database_config.POOL_TIMEOUT,
    pool_recycle=database_config.POOL_RECYCLE,
)

SessionLocal = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)


# FastAPI dependency — the request owns the transaction and commits explicitly
# (route-facing services call `await self.db.commit()`); closing the session
# rolls back anything left uncommitted.
async def get_db() -> AsyncGenerator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


AsyncDb = Annotated[AsyncSession, Depends(get_db)]


# Unit of work for Celery tasks — commits on success, rolls back on error.
@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
