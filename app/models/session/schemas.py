from app.models.base.schemas import Base


################################################################################
# POST /api/v1/auth/login #
################################################################################


class LoginRequest(Base):
    email: str


################################################################################
# POST /api/v1/auth/magic-link/verify #
################################################################################


class MagicLinkVerifyRequest(Base):
    token: str


################################################################################
# POST /api/v1/auth/token #
################################################################################


class TokenResponse(Base):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


################################################################################
# POST /api/v1/auth/logout #
################################################################################


class LogoutRequest(Base):
    refresh_token: str
    access_token: str | None = None


################################################################################
# POST /api/v1/auth/refresh #
################################################################################


class RefreshRequest(Base):
    refresh_token: str


class RefreshAccessTokenResponse(Base):
    access_token: str
    token_type: str = "bearer"
