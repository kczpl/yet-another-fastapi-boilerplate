import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, column, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.utils.time import utc_now

# Example model. Conventions (UUIDv7 PK, tz-aware timestamps, String+CheckConstraint
# instead of ENUM, public schema) are documented in .claude/rules/backend/database.md.

VALID_ITEM_STATUSES = ("active", "archived")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        # Short constraint name — the naming convention expands it to "items_status_check".
        CheckConstraint(column("status").in_(VALID_ITEM_STATUSES), name="status"),
        {"schema": "public"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7, server_default=text("uuidv7()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now, server_default=text("now()")
    )
