from app.models.base.schemas import Base
from pydantic import EmailStr, Field


################################################################################
# POST /api/v1/auth/login #
################################################################################


class LoginRequest(Base):
    email: EmailStr = Field(max_length=254, description="Valid email address")


################################################################################
# POST /api/v1/auth/magic-link/verify #
################################################################################


class MagicLinkVerifyRequest(Base):
    token: str = Field(min_length=1, max_length=1000, description="Magic link token")


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
    refresh_token: str = Field(min_length=1, max_length=1000, description="JWT refresh token")
    access_token: str | None = Field(None, max_length=1000, description="JWT access token")


################################################################################
# POST /api/v1/auth/refresh #
################################################################################


class RefreshRequest(Base):
    refresh_token: str = Field(min_length=1, max_length=1000, description="JWT refresh token")


class RefreshAccessTokenResponse(Base):
    access_token: str
    token_type: str = "bearer"
