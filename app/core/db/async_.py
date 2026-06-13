from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis as AsyncRedisClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import database_config
from app.core.db.base import _to_psycopg_url

################################################################################
# Postgres #
################################################################################


async_engine = create_async_engine(
    _to_psycopg_url(database_config.DATABASE_URL),
    echo=False,
    pool_pre_ping=True,
    pool_size=database_config.POOL_SIZE,
    max_overflow=database_config.POOL_MAX_OVERFLOW,
    pool_timeout=database_config.POOL_TIMEOUT,
    pool_recycle=database_config.POOL_RECYCLE,
)

AsyncSessionLocal = async_sessionmaker(
    autoflush=False,
    expire_on_commit=False,
    bind=async_engine,
    class_=AsyncSession,
)


# FastAPI dependency — the request owns the transaction and commits explicitly
# (route-facing services call `await self.db.commit()`).
async def _get_async_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


AsyncDb = Annotated[AsyncSession, Depends(_get_async_db)]


# Context manager for Celery tasks — auto-commits on success, rolls back on error.
@asynccontextmanager
async def async_db_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


################################################################################
# Redis (Celery broker + idempotency markers) #
################################################################################

async_redis = AsyncRedisClient.from_url(
    database_config.REDIS_URL,
    decode_responses=True,
)


async def _get_async_redis() -> AsyncGenerator[AsyncRedisClient]:
    yield async_redis


AsyncRedis = Annotated[AsyncRedisClient, Depends(_get_async_redis)]
