from app.core.db.async_ import (
    AsyncDb,
    AsyncRedis,
    AsyncSessionLocal,
    _get_async_db,
    _get_async_redis,
    async_db_session,
    async_engine,
    async_redis,
)
from app.core.db.base import Base, metadata

__all__ = [
    "AsyncDb",
    "AsyncRedis",
    "AsyncSessionLocal",
    "Base",
    "_get_async_db",
    "_get_async_redis",
    "async_db_session",
    "async_engine",
    "async_redis",
    "metadata",
]

# Import all models so SQLAlchemy can resolve relationships and Base.metadata is
# fully populated (used by Alembic autogenerate and the test schema builder).
import app.repositories  # noqa: F401
