from sqlalchemy.orm import DeclarativeBase

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from typing import AsyncGenerator
from app.core.config import config

engine = create_async_engine(
    config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    # echo=True,
    echo=False,
    pool_pre_ping=True,  # test connections before use (handles dropped connections).
    pool_size=15,  # maximum number of connections in the pool
    max_overflow=5,  # allow up to 5 additional connections during burst traffic (total: 20)
    pool_timeout=30,  # timeout after 30 seconds if no connection is available
    pool_recycle=3600,  # recycle connections after 1 hour to prevent stale connections
)


# SessionLocal is a factory for creating database sessions #
AsyncSessionLocal = async_sessionmaker(
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
    class_=AsyncSession,
)


# SQLAlchemy declarative base - all ORM models inherit from this #
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
