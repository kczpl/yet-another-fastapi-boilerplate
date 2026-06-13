from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# PostgreSQL naming convention for constraints and indexes.
# See .claude/rules/backend/database.md for the conventions these produce.
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(table_name)s_%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata


def _to_psycopg_url(url: str) -> str:
    # Normalize any common Postgres URL flavor onto the async psycopg3 driver.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url
