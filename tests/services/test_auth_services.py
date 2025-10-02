import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.auth import SendMagicLinkService, VerifyMagicLinkService, RefreshAccessTokenService, LogoutService
from app.core.exceptions import APIException
from app.models.user.models import User
from app.models.session.models import MagicLinkToken, UserSession
from app.utils.jwt import get_token_jti, create_refresh_token, create_access_token
from tests.fixtures.auth import *  # noqa: F403, F401


# ################################################################################
# # SendMagicLinkService tests #
# ################################################################################


@pytest.mark.asyncio
async def test_send_magic_link_service_success(test_session: AsyncSession, test_user: User, mocker):
    """Test SendMagicLinkService successfully sends magic link."""
    # Mock email sending
    mock_send_email = mocker.patch("app.services.auth.send_login_email")
    mock_send_email.return_value = "message-id-123"

    service = SendMagicLinkService(test_session)
    result = await service.call(test_user.email)

    # SendMagicLinkService returns a JSONResponse, check status code
    assert result.status_code == 200

    # Verify email was called with correct parameters
    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args
    assert test_user.email in call_args[1]["recipient_address"]
    assert "magic_link_url" in call_args[1]
    assert call_args[1]["language"] == test_user.language


@pytest.mark.asyncio
async def test_send_magic_link_service_user_not_found(test_session: AsyncSession, mocker):
    """Test SendMagicLinkService raises error for non-existent user."""
    mock_send_email = mocker.patch("app.services.auth.send_login_email")

    service = SendMagicLinkService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call("nonexistent@example.com")

    assert exc_info.value.status_code == 404
    mock_send_email.assert_not_called()


@pytest.mark.asyncio
async def test_send_magic_link_service_email_failure(test_session: AsyncSession, test_user: User, mocker):
    """Test SendMagicLinkService handles email sending failure."""
    # Mock email sending to fail
    mock_send_email = mocker.patch("app.services.auth.send_login_email")
    mock_send_email.return_value = None  # Indicates failure

    service = SendMagicLinkService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call(test_user.email)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_send_magic_link_invalidates_old_links(
    test_session: AsyncSession, test_user: User, test_magic_link_token: MagicLinkToken, mocker
):
    """Test SendMagicLinkService invalidates previous magic links."""
    from sqlalchemy import select

    # Mock time to ensure different token generation
    import time

    mocker.patch("time.time", return_value=time.time() + 100)

    # Mock email sending
    mock_send_email = mocker.patch("app.services.auth.send_login_email")
    mock_send_email.return_value = "message-id-123"

    # Verify existing token is not used
    assert test_magic_link_token.used is False

    service = SendMagicLinkService(test_session)
    result = await service.call(test_user.email)

    # Verify the service call succeeded
    assert result.status_code == 200

    # Refresh the session to get updated data
    await test_session.refresh(test_magic_link_token)

    # Check that old token was invalidated
    assert test_magic_link_token.used is True


# ################################################################################
# # VerifyMagicLinkService tests #
# ################################################################################


@pytest.mark.asyncio
async def test_verify_magic_link_service_success(
    test_session: AsyncSession, test_user: User, test_magic_link_token: MagicLinkToken
):
    """Test VerifyMagicLinkService successfully verifies token and creates session."""
    service = VerifyMagicLinkService(test_session)
    result = await service.call(test_magic_link_token.token, ip_address="192.168.1.1", user_agent="TestBrowser/2.0")

    assert "access_token" in result
    assert "refresh_token" in result

    # Verify session was created with correct details
    from sqlalchemy import select

    refresh_jti = get_token_jti(result["refresh_token"])
    session_result = await test_session.execute(select(UserSession).where(UserSession.jti == refresh_jti))
    session = session_result.scalar_one()
    assert session.user_id == test_user.id
    assert session.ip_address == "192.168.1.1"
    assert session.user_agent == "TestBrowser/2.0"


@pytest.mark.asyncio
async def test_verify_magic_link_service_invalid_token(test_session: AsyncSession):
    """Test VerifyMagicLinkService raises error for invalid token."""
    service = VerifyMagicLinkService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call("invalid-token")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_magic_link_service_expired_token(
    test_session: AsyncSession, test_user: User, test_expired_magic_link_token: MagicLinkToken
):
    """Test VerifyMagicLinkService raises error for expired token."""
    service = VerifyMagicLinkService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call(test_expired_magic_link_token.token)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_magic_link_service_used_token(
    test_session: AsyncSession, test_user: User, test_used_magic_link_token: MagicLinkToken
):
    """Test VerifyMagicLinkService raises error for already used token."""
    service = VerifyMagicLinkService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call(test_used_magic_link_token.token)

    assert exc_info.value.status_code == 400


# ################################################################################
# # RefreshAccessTokenService tests #
# ################################################################################


@pytest.mark.asyncio
async def test_refresh_access_token_service_success(
    test_session: AsyncSession, test_user: User, test_tokens: dict, test_user_session: UserSession
):
    """Test RefreshAccessTokenService successfully returns new access token."""
    service = RefreshAccessTokenService(test_session)
    result = await service.call(test_tokens["refresh_token"])

    # RefreshAccessTokenService returns RefreshAccessTokenResponse (Pydantic model)
    assert hasattr(result, "access_token")
    assert result.access_token != test_tokens["access_token"]

    # Verify the new access token has correct claims
    from app.utils.jwt import verify_token

    payload = verify_token(result.access_token, expected_type="access")
    assert payload["email"] == test_user.email
    assert payload["sub"] == str(test_user.id)
    assert payload["role"] == test_user.role.value


@pytest.mark.asyncio
async def test_refresh_access_token_service_blacklisted(
    test_session: AsyncSession, test_user: User, test_tokens: dict, test_user_session: UserSession
):
    """Test RefreshAccessTokenService raises error for blacklisted token."""
    from app.models.session.functions import blacklist_token

    # Blacklist the refresh token
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await blacklist_token(test_session, refresh_jti, "refresh", expires_at)

    service = RefreshAccessTokenService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call(test_tokens["refresh_token"])

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_access_token_service_no_session(test_session: AsyncSession, test_user: User):
    """Test RefreshAccessTokenService raises error when session doesn't exist."""
    # Create a refresh token without creating a session
    token_data = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role.value,
    }
    refresh_token = create_refresh_token(token_data)

    service = RefreshAccessTokenService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call(refresh_token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_access_token_service_wrong_token_type(
    test_session: AsyncSession, test_user: User, test_tokens: dict
):
    """Test RefreshAccessTokenService raises error for access token instead of refresh."""
    service = RefreshAccessTokenService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call(test_tokens["access_token"])  # Wrong type

    assert exc_info.value.status_code == 401


# ################################################################################
# # LogoutService tests #
# ################################################################################


@pytest.mark.asyncio
async def test_logout_service_success(
    test_session: AsyncSession, test_user: User, test_tokens: dict, test_user_session: UserSession
):
    """Test LogoutService successfully blacklists tokens and deletes session."""
    from sqlalchemy import select
    from app.models.session.models import TokenBlacklist

    service = LogoutService(test_session)
    result = await service.call(test_tokens["refresh_token"], test_tokens["access_token"])

    assert result is True

    # Verify session was deleted
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    session_result = await test_session.execute(select(UserSession).where(UserSession.jti == refresh_jti))
    assert session_result.scalar_one_or_none() is None

    # Verify refresh token was blacklisted
    blacklist_result = await test_session.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == refresh_jti, TokenBlacklist.token_type == "refresh")
    )
    assert blacklist_result.scalar_one_or_none() is not None

    # Verify access token was blacklisted
    access_jti = get_token_jti(test_tokens["access_token"])
    blacklist_result = await test_session.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == access_jti, TokenBlacklist.token_type == "access")
    )
    assert blacklist_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_logout_service_without_access_token(
    test_session: AsyncSession, test_user: User, test_tokens: dict, test_user_session: UserSession
):
    """Test LogoutService works with only refresh token."""
    from sqlalchemy import select
    from app.models.session.models import TokenBlacklist

    service = LogoutService(test_session)
    result = await service.call(test_tokens["refresh_token"])

    assert result is True

    # Verify session was deleted
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    session_result = await test_session.execute(select(UserSession).where(UserSession.jti == refresh_jti))
    assert session_result.scalar_one_or_none() is None

    # Verify only refresh token was blacklisted
    blacklist_result = await test_session.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == refresh_jti, TokenBlacklist.token_type == "refresh")
    )
    assert blacklist_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_logout_service_invalid_token(test_session: AsyncSession):
    """Test LogoutService raises error for invalid token."""
    service = LogoutService(test_session)

    with pytest.raises(APIException) as exc_info:
        await service.call("invalid-token")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_logout_service_already_blacklisted(
    test_session: AsyncSession, test_user: User, test_tokens: dict, test_user_session: UserSession
):
    """Test LogoutService handles already blacklisted token."""
    from app.models.session.functions import blacklist_token

    # Blacklist the token first
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await blacklist_token(test_session, refresh_jti, "refresh", expires_at)

    service = LogoutService(test_session)

    # Should raise error because token is already blacklisted
    with pytest.raises(APIException) as exc_info:
        await service.call(test_tokens["refresh_token"])

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_logout_service_calculates_expiry_correctly(test_session: AsyncSession, test_user: User, mocker):
    """Test LogoutService correctly calculates token expiry times."""
    from sqlalchemy import select
    from app.models.session.models import TokenBlacklist

    # Create tokens with known expiry
    token_data = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role.value,
    }

    # Create tokens
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=15))
    refresh_token = create_refresh_token(token_data)

    # Create session for the refresh token
    from app.models.session.functions import create_user_session

    await create_user_session(test_session, test_user.id, refresh_token)

    service = LogoutService(test_session)
    result = await service.call(refresh_token, access_token)

    assert result is True

    # Verify both tokens were blacklisted with proper expiry
    refresh_jti = get_token_jti(refresh_token)
    access_jti = get_token_jti(access_token)

    # Check refresh token blacklist entry
    result = await test_session.execute(select(TokenBlacklist).where(TokenBlacklist.jti == refresh_jti))
    refresh_blacklist = result.scalar_one()
    assert refresh_blacklist.expires_at > datetime.now(timezone.utc)

    # Check access token blacklist entry
    result = await test_session.execute(select(TokenBlacklist).where(TokenBlacklist.jti == access_jti))
    access_blacklist = result.scalar_one()
    assert access_blacklist.expires_at > datetime.now(timezone.utc)
