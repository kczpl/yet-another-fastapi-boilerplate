from fastapi import APIRouter, status, Depends
from app.models.session.schemas import (
    LoginRequest,
    LoginResponse,
    MagicLinkVerifyRequest,
    TokenResponse,
    RefreshRequest,
    RefreshAccessTokenResponse,
    LogoutRequest,
    LogoutResponse,
)
from app.api.deps import get_client_info
from app.services.auth import SendMagicLinkService, VerifyMagicLinkService, RefreshAccessTokenService, LogoutService


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(req: LoginRequest, service: SendMagicLinkService = Depends()):
    return await service.call(req.email)


@router.post("/verify-token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def verify_token(
    req: MagicLinkVerifyRequest,
    client_info: dict = Depends(get_client_info),
    service: VerifyMagicLinkService = Depends(),
):
    return await service.call(req.token, client_info.get("ip_address"), client_info.get("user_agent"))


@router.post("/refresh", response_model=RefreshAccessTokenResponse, status_code=status.HTTP_200_OK)
async def refresh_access_token(
    request: RefreshRequest,
    auth: RefreshAccessTokenService = Depends(),
):
    return await auth.call(request.refresh_token)


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    request: LogoutRequest,
    auth: LogoutService = Depends(),
):
    return await auth.call(request.refresh_token, request.access_token)
