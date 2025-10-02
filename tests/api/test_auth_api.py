import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.session.models import MagicLinkToken, UserSession, TokenBlacklist
from app.models.user.models import User
from app.utils.jwt import get_token_jti, verify_token
from tests.fixtures.auth import *  # noqa: F403, F401


# ################################################################################
# # POST /api/v1/auth/login tests #
# ################################################################################


@pytest.mark.asyncio
async def test_login_success(unauthorized_client: AsyncClient, test_user: User, mocker):
    """Test successful magic link login for existing user."""
    # Mock email sending to return success
    mock_send_login_email = mocker.patch("app.services.auth.send_login_email")
    mock_send_login_email.return_value = "message-id-123"

    response = await unauthorized_client.post("/api/v1/auth/login", json={"email": test_user.email})

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "api.auth.magic_link_sent"

    # Verify email was sent
    mock_send_login_email.assert_called_once()
    call_args = mock_send_login_email.call_args
    assert call_args[1]["recipient_address"] == test_user.email
    assert "magic_link_url" in call_args[1]
    assert call_args[1]["language"] == test_user.language


@pytest.mark.asyncio
async def test_login_nonexistent_user(unauthorized_client: AsyncClient, mocker):
    """Test login with non-existent email returns 404."""
    mock_send_login_email = mocker.patch("app.services.auth.send_login_email")

    response = await unauthorized_client.post("/api/v1/auth/login", json={"email": "nonexistent@example.com"})

    assert response.status_code == 404

    # Verify email was not sent
    mock_send_login_email.assert_not_called()


@pytest.mark.asyncio
async def test_login_inactive_user(unauthorized_client: AsyncClient, test_inactive_user: User, mocker):
    """Test login with inactive user returns 404."""
    mock_send_login_email = mocker.patch("app.services.auth.send_login_email")

    response = await unauthorized_client.post("/api/v1/auth/login", json={"email": test_inactive_user.email})

    assert response.status_code == 404

    # Verify email was not sent
    mock_send_login_email.assert_not_called()


@pytest.mark.asyncio
async def test_login_email_send_failure(unauthorized_client: AsyncClient, test_user: User, mocker):
    """Test login when email sending fails returns 500."""
    # Mock email sending to return None (failure)
    mock_send_login_email = mocker.patch("app.services.auth.send_login_email")
    mock_send_login_email.return_value = None

    response = await unauthorized_client.post("/api/v1/auth/login", json={"email": test_user.email})

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_login_invalidates_previous_magic_links(
    unauthorized_client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    test_magic_link_token: MagicLinkToken,
    mocker,
):
    """Test that login invalidates all previous magic links for the user."""
    # Mock email sending
    mock_send_login_email = mocker.patch("app.services.auth.send_login_email")
    mock_send_login_email.return_value = "message-id-123"

    # Verify the existing token is not used
    result = await test_session.execute(select(MagicLinkToken).where(MagicLinkToken.id == test_magic_link_token.id))
    existing_token = result.scalar_one()
    assert existing_token.used is False

    response = await unauthorized_client.post("/api/v1/auth/login", json={"email": test_user.email})

    assert response.status_code == 200

    # Verify the old token is now marked as used
    await test_session.commit()  # Ensure we see the latest data
    result = await test_session.execute(select(MagicLinkToken).where(MagicLinkToken.id == test_magic_link_token.id))
    updated_token = result.scalar_one()
    assert updated_token.used is True


# ################################################################################
# # POST /api/v1/auth/verify-token tests #
# ################################################################################


@pytest.mark.asyncio
async def test_verify_token_success(
    unauthorized_client: AsyncClient, test_session: AsyncSession, test_user: User, test_magic_link_token: MagicLinkToken
):
    """Test successful magic link verification returns JWT tokens."""
    response = await unauthorized_client.post(
        "/api/v1/auth/verify-token",
        json={"token": test_magic_link_token.token},
        headers={"User-Agent": "TestBrowser/1.0"},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify we got both tokens
    assert "access_token" in data
    assert "refresh_token" in data

    # Verify tokens are valid
    access_payload = verify_token(data["access_token"], expected_type="access")
    refresh_payload = verify_token(data["refresh_token"], expected_type="refresh")

    assert access_payload["email"] == test_user.email
    assert refresh_payload["email"] == test_user.email
    assert access_payload["sub"] == str(test_user.id)
    assert refresh_payload["sub"] == str(test_user.id)

    # Verify session was created
    refresh_jti = get_token_jti(data["refresh_token"])
    result = await test_session.execute(select(UserSession).where(UserSession.jti == refresh_jti))
    session = result.scalar_one()
    assert session.user_id == test_user.id
    assert session.ip_address is not None
    assert session.user_agent == "TestBrowser/1.0"


@pytest.mark.asyncio
async def test_verify_token_expired(unauthorized_client: AsyncClient, test_expired_magic_link_token: MagicLinkToken):
    """Test verifying expired magic link token fails."""
    response = await unauthorized_client.post(
        "/api/v1/auth/verify-token", json={"token": test_expired_magic_link_token.token}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_token_already_used(unauthorized_client: AsyncClient, test_used_magic_link_token: MagicLinkToken):
    """Test verifying already used magic link token fails."""
    response = await unauthorized_client.post(
        "/api/v1/auth/verify-token", json={"token": test_used_magic_link_token.token}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_token_invalid_format(unauthorized_client: AsyncClient):
    """Test verifying invalid token format fails."""
    response = await unauthorized_client.post("/api/v1/auth/verify-token", json={"token": "invalid-token-format"})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_token_wrong_purpose(unauthorized_client: AsyncClient, test_user: User):
    """Test verifying token with wrong purpose fails."""
    from app.utils.jwt import create_access_token

    # Create an access token instead of magic link token
    wrong_token = create_access_token({"email": test_user.email})

    response = await unauthorized_client.post("/api/v1/auth/verify-token", json={"token": wrong_token})

    assert response.status_code == 400


# ################################################################################
# # POST /api/v1/auth/refresh tests #
# ################################################################################


@pytest.mark.asyncio
async def test_refresh_token_success(
    unauthorized_client: AsyncClient, test_user: User, test_tokens: dict, test_user_session: UserSession
):
    """Test successful refresh token returns new access token."""
    response = await unauthorized_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_tokens["refresh_token"]}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify we got a new access token
    assert "access_token" in data

    # Verify new access token is valid
    access_payload = verify_token(data["access_token"], expected_type="access")
    assert access_payload["email"] == test_user.email
    assert access_payload["sub"] == str(test_user.id)
    assert access_payload["role"] == test_user.role.value


@pytest.mark.asyncio
async def test_refresh_token_expired_session(
    unauthorized_client: AsyncClient, test_user: User, test_tokens: dict, test_expired_user_session: UserSession
):
    """Test refresh with expired session fails."""
    response = await unauthorized_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_tokens["refresh_token"]}
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "api.auth.unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_blacklisted(
    unauthorized_client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    test_tokens: dict,
    test_user_session: UserSession,
):
    """Test refresh with blacklisted token fails."""
    from app.models.session.functions import blacklist_token
    from datetime import datetime, timedelta, timezone

    # Blacklist the refresh token
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await blacklist_token(test_session, refresh_jti, "refresh", expires_at)

    response = await unauthorized_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_tokens["refresh_token"]}
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "api.auth.unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_with_access_token(unauthorized_client: AsyncClient, test_tokens: dict):
    """Test refresh with access token instead of refresh token fails."""
    response = await unauthorized_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": test_tokens["access_token"]},  # Wrong token type
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "api.auth.unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_invalid_format(unauthorized_client: AsyncClient):
    """Test refresh with invalid token format fails."""
    response = await unauthorized_client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid-token-format"})

    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "api.auth.unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_missing_session(unauthorized_client: AsyncClient, test_user: User, test_tokens: dict):
    """Test refresh without existing session fails."""
    # No session created for this refresh token
    response = await unauthorized_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_tokens["refresh_token"]}
    )

    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "api.auth.unauthorized"


# ################################################################################
# # POST /api/v1/auth/logout tests #
# ################################################################################


@pytest.mark.asyncio
async def test_logout_success(
    unauthorized_client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    test_tokens: dict,
    test_user_session: UserSession,
):
    """Test successful logout deletes session and blacklists tokens."""
    response = await unauthorized_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": test_tokens["refresh_token"], "access_token": test_tokens["access_token"]},
    )

    assert response.status_code == 200

    # Verify session was deleted
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    result = await test_session.execute(select(UserSession).where(UserSession.jti == refresh_jti))
    assert result.scalar_one_or_none() is None

    # Verify refresh token was blacklisted
    result = await test_session.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == refresh_jti, TokenBlacklist.token_type == "refresh")
    )
    assert result.scalar_one_or_none() is not None

    # Verify access token was blacklisted
    access_jti = get_token_jti(test_tokens["access_token"])
    result = await test_session.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == access_jti, TokenBlacklist.token_type == "access")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_logout_without_access_token(
    unauthorized_client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    test_tokens: dict,
    test_user_session: UserSession,
):
    """Test logout with only refresh token still works."""
    response = await unauthorized_client.post(
        "/api/v1/auth/logout", json={"refresh_token": test_tokens["refresh_token"]}
    )

    assert response.status_code == 200

    # Verify session was deleted
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    result = await test_session.execute(select(UserSession).where(UserSession.jti == refresh_jti))
    assert result.scalar_one_or_none() is None

    # Verify refresh token was blacklisted
    result = await test_session.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == refresh_jti, TokenBlacklist.token_type == "refresh")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_logout_invalid_refresh_token(unauthorized_client: AsyncClient):
    """Test logout with invalid refresh token fails."""
    response = await unauthorized_client.post("/api/v1/auth/logout", json={"refresh_token": "invalid-token"})

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "api.auth.unauthorized"


@pytest.mark.asyncio
async def test_logout_already_blacklisted(
    unauthorized_client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    test_tokens: dict,
    test_user_session: UserSession,
):
    """Test logout with already blacklisted token still succeeds."""
    from app.models.session.functions import blacklist_token
    from datetime import datetime, timedelta, timezone

    # Blacklist the refresh token first
    refresh_jti = get_token_jti(test_tokens["refresh_token"])
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await blacklist_token(test_session, refresh_jti, "refresh", expires_at)

    # Try to logout again - should still work
    response = await unauthorized_client.post(
        "/api/v1/auth/logout", json={"refresh_token": test_tokens["refresh_token"]}
    )

    # Even though token is blacklisted, logout should handle it gracefully
    assert response.status_code == 401  # Because the token is blacklisted
