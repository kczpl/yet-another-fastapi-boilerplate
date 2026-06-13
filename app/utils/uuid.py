from uuid import UUID

from uuid_utils.compat import uuid7 as _uuid7


def uuid7() -> UUID:
    # Timestamp-ordered UUIDv7 returned as a stdlib uuid.UUID so ORM-created rows
    # match the DB-side `uuidv7()` server default (Postgres 18+).
    return _uuid7()
