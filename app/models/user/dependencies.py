from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.db import get_db, AsyncSession
from app.utils.jwt import verify_token
from app.models.session.functions import is_token_blacklisted
from app.core.exceptions import raise_unauthorized
from app.core.errors import ERRORS
from app.core.logger import log
from app.models.user.functions import find_active_user_by_id
from app.models.user.schemas import CurrentUser
import sentry_sdk
import uuid


async def auth_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> CurrentUser:
    if not credentials or not credentials.credentials:
        raise_unauthorized(ERRORS["unauthorized"])

    payload = verify_token(credentials.credentials, expected_type="access")

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(db, jti):
        raise_unauthorized(ERRORS["unauthorized"])

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise_unauthorized(ERRORS["unauthorized"])

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        log.error("invalid user ID format in token", user_id=user_id_str)
        raise_unauthorized(ERRORS["unauthorized"])

    user = await find_active_user_by_id(db, user_id)

    scope = sentry_sdk.get_current_scope()
    scope.set_user({"id": str(user.id), "email": user.email})

    return CurrentUser(
        id=str(user.id),
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )
