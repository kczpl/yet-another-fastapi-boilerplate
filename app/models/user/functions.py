from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user.models import User
from app.core.exceptions import raise_not_found
from app.core.errors import ERRORS
import uuid


async def find_active_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id, User.is_active))
    user = result.scalar_one_or_none()
    if not user:
        raise_not_found(ERRORS["not_found"])
    return user


async def find_active_user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email, User.is_active))
    user = result.scalar_one_or_none()
    if not user:
        raise_not_found(ERRORS["not_found"])
    return user
