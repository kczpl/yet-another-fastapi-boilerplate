from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import database_config

# PostgreSQL naming convention for indexes #
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)

engine = create_async_engine(
    database_config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_pre_ping=True,  # test connections before use (handles dropped connections).
    pool_size=15,  # maximum number of connections in the pool
    max_overflow=5,  # allow up to 5 additional connections during burst traffic (total: 20)
    pool_timeout=30,  # timeout after 30 seconds if no connection is available
    pool_recycle=3600,  # recycle connections after 1 hour to prevent stale connections
)


AsyncSessionLocal = async_sessionmaker[AsyncSession](
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
    class_=AsyncSession,
)


# SQLAlchemy declarative base - all ORM models inherit from this #
class Base(DeclarativeBase):
    metadata = metadata


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
