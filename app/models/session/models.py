from app.core.db import Base
from sqlalchemy import ForeignKey, Text, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.models.user.models import User


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE")
    )
    ip_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Track IP
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Track device
    jti: Mapped[str] = mapped_column(Text, unique=True)  # JWT ID for token tracking
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    token: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="magic_links")


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti: Mapped[str] = mapped_column(Text, unique=True)  # JWT ID
    token_type: Mapped[str] = mapped_column(Text)  # access or refresh
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
