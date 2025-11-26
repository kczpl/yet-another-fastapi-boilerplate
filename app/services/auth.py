from datetime import datetime, timedelta, timezone
from typing import Optional
from app.services.base import Service
from app.utils.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token_with_blacklist,
    verify_magic_link_token,
    get_token_jti,
)
from app.utils.emails import send_login_email
from app.core.logger import log
from app.core.config import config
from app.core.exceptions import (
    raise_bad_request,
    raise_unauthorized,
    raise_server_error,
)
from app.core.errors import ERRORS
from app.models.user.functions import find_active_user_by_email
from app.models.session.functions import (
    invalidate_user_magic_links,
    create_magic_link,
    get_magic_link,
    create_user_session,
    get_user_session_by_jti,
    delete_user_session,
    blacklist_token,
)

################################################################################
# POST /api/v1/auth/login #
################################################################################


################################################################################
# POST /api/v1/auth/magic-link #
################################################################################


class SendMagicLinkService(Service):
    async def call(self, email: str) -> dict:
        user = await find_active_user_by_email(self.db, email)

        await invalidate_user_magic_links(self.db, user.id)
        magic_token = await create_magic_link(self.db, email, user.id)

        magic_link_url = f"https://{config.FRONTEND_DOMAIN}/auth/verify?token={magic_token}"
        email_sent = send_login_email(recipient_address=email, magic_link_url=magic_link_url, language=user.language)

        if not email_sent:
            log.error("failed to send magic link email", user_id=str(user.id), email=email)
            raise_server_error(ERRORS["magic_link_send_failed"])

        log.info("magic link sent", user_id=str(user.id), email=email)
        return {"message": "api.auth.magic_link_sent"}


################################################################################
# POST /api/v1/auth/magic-link/verify #
################################################################################


class VerifyMagicLinkService(Service):
    async def call(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        email = verify_magic_link_token(token)
        user = await find_active_user_by_email(self.db, email)
        magic_link_token = await get_magic_link(self.db, token, user.id)
        await invalidate_user_magic_links(self.db, magic_link_token.user_id)

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        await create_user_session(self.db, user.id, refresh_token, ip_address, user_agent)
        log.info("magic link verified and tokens created", user_id=str(user.id), email=email)

        return {"access_token": access_token, "refresh_token": refresh_token}


################################################################################
# POST /api/v1/auth/refresh-access-token #
################################################################################


class RefreshAccessTokenService(Service):
    async def call(self, refresh_token: str) -> dict:
        payload = await verify_token_with_blacklist(self.db, refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        jti = payload.get("jti")

        if not user_id or not jti:
            raise_unauthorized(ERRORS["unauthorized"])

        log.info("refresh access token", user_id=user_id, jti=jti)

        user_session = await get_user_session_by_jti(self.db, jti)
        if not user_session:
            log.warning("refresh token not found or expired", jti=jti)
            raise_unauthorized(ERRORS["unauthorized"])

        user = await find_active_user_by_email(self.db, payload.get("email"))
        if not user or str(user.id) != user_id:
            log.warning(f"refresh token for non-existent user: {user_id}")
            raise_unauthorized(ERRORS["unauthorized"])

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }

        access_token = create_access_token(token_data)
        return {"access_token": access_token}


################################################################################
# POST /api/v1/auth/logout #
################################################################################


class LogoutService(Service):
    async def call(self, refresh_token: str, access_token: Optional[str] = None) -> dict:
        refresh_jti = get_token_jti(refresh_token)
        if not refresh_jti:
            raise_bad_request(ERRORS["unauthorized"])

        deleted_count = await delete_user_session(self.db, refresh_jti)

        await self._blacklist_refresh_token(refresh_token, refresh_jti)

        if access_token:
            await self._blacklist_access_token(access_token)

        log.info("user logged out", refresh_jti=refresh_jti[:8], sessions_deleted=deleted_count)
        return {"message": "api.auth.logged_out_successfully"}

    async def _blacklist_refresh_token(self, refresh_token: str, jti: str) -> None:
        payload = await verify_token_with_blacklist(self.db, refresh_token, expected_type="refresh")
        expires_at = self._get_token_expires_at(payload, timedelta(days=7))
        await blacklist_token(self.db, jti, "refresh", expires_at)

    async def _blacklist_access_token(self, access_token: str) -> None:
        access_jti = get_token_jti(access_token)
        if not access_jti:
            return

        payload = await verify_token_with_blacklist(self.db, access_token, expected_type="access")
        expires_at = self._get_token_expires_at(payload, timedelta(minutes=15))
        await blacklist_token(self.db, access_jti, "access", expires_at)

    def _get_token_expires_at(self, payload: dict, default_delta: timedelta) -> datetime:
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, timezone.utc)
        return datetime.now(timezone.utc) + default_delta
