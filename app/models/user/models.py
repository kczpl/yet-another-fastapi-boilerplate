import uuid
from datetime import datetime
from sqlalchemy import DateTime, Text, Boolean, text, Enum
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from typing import TYPE_CHECKING, List
from app.core.db import Base

if TYPE_CHECKING:
    from app.models.session.models import UserSession, MagicLinkToken


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), server_default="member")
    language: Mapped[str] = mapped_column(Text, server_default="pl")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    # relationships
    sessions: Mapped[List["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    magic_links: Mapped[List["MagicLinkToken"]] = relationship("MagicLinkToken", back_populates="user", cascade="all, delete-orphan")
