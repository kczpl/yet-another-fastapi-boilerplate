from app.core.db.async_ import (
    AsyncDb,
    AsyncSessionLocal,
    _get_async_db,
    async_db_session,
    async_engine,
)
from app.core.db.base import Base, metadata

__all__ = [
    "AsyncDb",
    "AsyncSessionLocal",
    "Base",
    "_get_async_db",
    "async_db_session",
    "async_engine",
    "metadata",
]

# Import all models so SQLAlchemy can resolve relationships and Base.metadata is
# fully populated (used by Alembic autogenerate and the test schema builder).
import app.repositories  # noqa: F401
