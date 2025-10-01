import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import auth_config
from app.core.exceptions import raise_unauthorized, raise_bad_request
from app.core.errors import ERRORS
from jose import JWTError, jwt
from app.core.logger import log
from app.models.session.models import TokenBlacklist
from sqlalchemy.ext.asyncio import AsyncSession

ACCESS_TOKEN_EXPIRE_MINUTES = auth_config.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = auth_config.REFRESH_TOKEN_EXPIRE_DAYS
MAGIC_LINK_EXPIRE_MINUTES = auth_config.MAGIC_LINK_EXPIRE_MINUTES
JWT_SECRET_KEY = auth_config.JWT_SECRET_KEY
JWT_ALGORITHM = auth_config.JWT_ALGORITHM


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "type": "access",
            "jti": str(uuid.uuid4()),  # JWT ID for token tracking #
        }
    )
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": str(uuid.uuid4()),  # JWT ID for token tracking #
        }
    )
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_type = payload.get("type")
        if token_type != expected_type:
            raise_unauthorized(ERRORS["unauthorized"])

        exp = payload.get("exp")
        if exp is None:
            raise_unauthorized(ERRORS["unauthorized"])

        if datetime.now(timezone.utc) > datetime.fromtimestamp(exp, timezone.utc):
            raise_unauthorized(ERRORS["unauthorized"])

        return payload
    except JWTError:
        raise_unauthorized(ERRORS["unauthorized"])


async def verify_token_with_blacklist(db, token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_type = payload.get("type")
        if token_type != expected_type:
            raise_unauthorized(ERRORS["unauthorized"])

        exp = payload.get("exp")
        if exp is None:
            raise_unauthorized(ERRORS["unauthorized"])

        if datetime.now(timezone.utc) > datetime.fromtimestamp(exp, timezone.utc):
            raise_unauthorized(ERRORS["unauthorized"])

        jti = payload.get("jti")
        if jti and await is_token_blacklisted(db, jti):
            raise_unauthorized(ERRORS["unauthorized"])

        return payload
    except JWTError:
        raise_unauthorized(ERRORS["unauthorized"])


def get_token_jti(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("jti")
    except JWTError:
        return None


async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    from sqlalchemy import select

    query = select(TokenBlacklist).where(
        TokenBlacklist.jti == jti, TokenBlacklist.expires_at > datetime.now(timezone.utc)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


################################################################################
# Magic link tokens #
################################################################################


def create_magic_link_token(email: str) -> str:
    data = {"email": email, "purpose": "magic_link"}
    expire = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
    data.update({"exp": expire})
    return jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_magic_link_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        purpose = payload.get("purpose")
        if purpose != "magic_link":
            raise_bad_request(ERRORS["invalid_magic_link_token"])

        email = payload.get("email")
        if not email:
            raise_bad_request(ERRORS["invalid_magic_link_token"])

        return email

    except JWTError:
        log.error("invalid magic link token")
        raise_bad_request(ERRORS["invalid_magic_link_token"])


################################################################################
# One-time tokens #
################################################################################


def create_onetime_token(email: str) -> str:
    data = {"email": email, "purpose": "onetime_form"}
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    data.update({"exp": expire})

    return jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_onetime_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        purpose = payload.get("purpose")
        if purpose != "onetime_form":
            raise_bad_request(ERRORS["invalid_one_time_token"])

        email = payload.get("email")
        if not email:
            raise_bad_request(ERRORS["invalid_one_time_token"])

        return email

    except JWTError:
        raise_bad_request(ERRORS["invalid_one_time_token"])
