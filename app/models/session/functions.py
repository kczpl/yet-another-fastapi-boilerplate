from app.models.session.models import MagicLinkToken, UserSession, TokenBlacklist
from app.utils.jwt import create_magic_link_token, get_token_jti
from app.core.exceptions import raise_bad_request
from app.core.errors import ERRORS
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import Optional
import uuid


async def create_magic_link(db: AsyncSession, email: str, user_id: uuid.UUID) -> str:
    magic_token = create_magic_link_token(email)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    magic_link_record = MagicLinkToken(user_id=user_id, token=magic_token, expires_at=expires_at)
    db.add(magic_link_record)
    await db.commit()
    return magic_token


async def get_magic_link(db: AsyncSession, token: str, user_id: uuid.UUID) -> MagicLinkToken:
    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.user_id == user_id,
            MagicLinkToken.token == token,
            ~MagicLinkToken.used,
            MagicLinkToken.expires_at > datetime.now(timezone.utc),
        )
    )
    magic_link = result.scalar_one_or_none()

    if not magic_link:
        raise_bad_request(ERRORS["magic_link_invalid_or_expired"])
    return magic_link


async def create_user_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    refresh_token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    refresh_jti = get_token_jti(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    user_session = UserSession(
        user_id=user_id,
        jti=refresh_jti,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(user_session)
    await db.commit()


async def invalidate_user_magic_links(db: AsyncSession, user_id: uuid.UUID) -> None:
    stmt = (
        update(MagicLinkToken).where(MagicLinkToken.user_id == user_id, ~MagicLinkToken.used).values(used=True)
    )
    await db.execute(stmt)
    await db.commit()


async def get_user_session_by_jti(db: AsyncSession, jti: str) -> Optional[UserSession]:
    stmt = select(UserSession).where(UserSession.jti == jti, UserSession.expires_at > datetime.now(timezone.utc))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_user_session(db: AsyncSession, jti: str) -> int:
    stmt = delete(UserSession).where(UserSession.jti == jti)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def blacklist_token(db: AsyncSession, jti: str, token_type: str, expires_at: datetime) -> None:
    blacklisted_token = TokenBlacklist(jti=jti, token_type=token_type, expires_at=expires_at)
    db.add(blacklisted_token)
    await db.commit()


async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    stmt = select(TokenBlacklist).where(
        TokenBlacklist.jti == jti, TokenBlacklist.expires_at > datetime.now(timezone.utc)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
