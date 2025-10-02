import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user.models import User, UserRole
from app.models.session.models import MagicLinkToken, UserSession
from app.utils.jwt import create_access_token, create_refresh_token, create_magic_link_token, get_token_jti


@pytest_asyncio.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create a test user in the database."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role=UserRole.member,
        language="en",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin_user(test_session: AsyncSession) -> User:
    """Create a test admin user in the database."""
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=UserRole.admin,
        language="en",
        is_active=True,
    )
    test_session.add(admin_user)
    await test_session.commit()
    await test_session.refresh(admin_user)
    return admin_user


@pytest_asyncio.fixture
async def test_inactive_user(test_session: AsyncSession) -> User:
    """Create an inactive test user in the database."""
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        role=UserRole.member,
        language="en",
        is_active=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_magic_link_token(test_session: AsyncSession, test_user: User) -> MagicLinkToken:
    """Create a valid magic link token for the test user."""
    token = create_magic_link_token(test_user.email)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    magic_link = MagicLinkToken(
        user_id=test_user.id,
        token=token,
        expires_at=expires_at,
        used=False,
    )
    test_session.add(magic_link)
    await test_session.commit()
    await test_session.refresh(magic_link)
    return magic_link


@pytest_asyncio.fixture
async def test_expired_magic_link_token(test_session: AsyncSession, test_user: User) -> MagicLinkToken:
    """Create an expired magic link token for the test user."""
    token = create_magic_link_token(test_user.email)
    expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # Already expired

    magic_link = MagicLinkToken(
        user_id=test_user.id,
        token=token,
        expires_at=expires_at,
        used=False,
    )
    test_session.add(magic_link)
    await test_session.commit()
    await test_session.refresh(magic_link)
    return magic_link


@pytest_asyncio.fixture
async def test_used_magic_link_token(test_session: AsyncSession, test_user: User) -> MagicLinkToken:
    """Create a used magic link token for the test user."""
    token = create_magic_link_token(test_user.email)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    magic_link = MagicLinkToken(
        user_id=test_user.id,
        token=token,
        expires_at=expires_at,
        used=True,  # Already used
    )
    test_session.add(magic_link)
    await test_session.commit()
    await test_session.refresh(magic_link)
    return magic_link


@pytest.fixture
def test_tokens(test_user: User) -> dict:
    """Generate valid access and refresh tokens for the test user."""
    token_data = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "role": test_user.role.value,
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_data": token_data,
    }


@pytest_asyncio.fixture
async def test_user_session(test_session: AsyncSession, test_user: User, test_tokens: dict) -> UserSession:
    """Create a user session in the database."""
    refresh_token = test_tokens["refresh_token"]
    refresh_jti = get_token_jti(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    session = UserSession(
        user_id=test_user.id,
        jti=refresh_jti,
        expires_at=expires_at,
        ip_address="127.0.0.1",
        user_agent="TestClient/1.0",
    )
    test_session.add(session)
    await test_session.commit()
    await test_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def test_expired_user_session(test_session: AsyncSession, test_user: User, test_tokens: dict) -> UserSession:
    """Create an expired user session in the database."""
    refresh_token = test_tokens["refresh_token"]
    refresh_jti = get_token_jti(refresh_token)
    expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # Already expired

    session = UserSession(
        user_id=test_user.id,
        jti=refresh_jti,
        expires_at=expires_at,
        ip_address="127.0.0.1",
        user_agent="TestClient/1.0",
    )
    test_session.add(session)
    await test_session.commit()
    await test_session.refresh(session)
    return session
