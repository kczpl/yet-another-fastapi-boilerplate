import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock
from contextlib import asynccontextmanager

from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pytest_mock import MockerFixture

# add the parent directory to the Python path so we can import from app #
sys.path.insert(0, str(Path(__file__).parent.parent))

################################################################################
# mock rate limiter #
################################################################################

# mock rate limiter to bypass rate limiting in tests #
mock_limiter = MagicMock()
mock_limiter.limit.return_value = lambda f: f  # Pass-through decorator
sys.modules["app.core.rate_limiter"] = MagicMock(limiter=mock_limiter)


################################################################################
# mock psycopg and pgqueuer #
################################################################################

# mock pgqueuer components
mock_sync_driver = MagicMock()
mock_sync_queries = MagicMock()
mock_sync_queries.enqueue = MagicMock(return_value="mock-job-id")
mock_sync_queries.dequeue = MagicMock(return_value=None)

sys.modules["pgqueuer.db"] = MagicMock(SyncPsycopgDriver=MagicMock(return_value=mock_sync_driver))
sys.modules["pgqueuer.queries"] = MagicMock(SyncQueries=MagicMock(return_value=mock_sync_queries))


# create mock lifespan that doesn't connect to external databases
@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    """Mock lifespan that doesn't connect to external databases."""
    # create mock sync queries object with common methods you might need
    mock_queries = MagicMock()
    mock_queries.enqueue = MagicMock(return_value="mock-job-id")  # sync method
    mock_queries.dequeue = MagicMock(return_value=None)  # sync method

    # set the mock queries in app.extra
    app.extra["pgq_queries"] = mock_queries
    yield


################################################################################
from app.main import app  # noqa: E402

app.router.lifespan_context = mock_lifespan

from app.core.db import get_db, Base  # noqa: E402
from app.core.auth import get_current_user  # noqa: E402
from app.core.pgqueuer_producer import get_queue  # noqa: E402
from app.schemas.user import CurrentUser  # noqa: E402
from app.models.user import User  # noqa: E402

TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/postgres?sslmode=disable"
TEST_JWT_SECRET_KEY = "test-jwt-secret-key"
TEST_JWT_ALGORITHM = "HS256"
MOCK_USER_ID = "4ef80032-9b19-4948-8f1f-69758f35a70a"
TEST_ENCRYPTION_SECRET_KEY = "test-encryption-secret-key"
TEST_ENCRYPTION_SALT = "test-encryption-salt"


@pytest.fixture(scope="function")
def test_engine():
    """Create test database engine for the session.

    Uses SQLAlchemy core engine for test database connection.
    Creates all tables defined in Base.metadata at session start.
    """
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # create all tables using SQLAlchemy Base metadata
    Base.metadata.create_all(engine)

    yield engine

    # clean up: drop all tables after test session
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a database session for each test function.

    Uses SQLAlchemy ORM Session for database operations.
    Automatically rolls back changes after each test to ensure isolation.
    """
    # create new session for this test
    SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=test_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        # rollback any uncommitted changes to keep tests isolated
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(test_session, mock_sync_queries):
    """Create a test client with database session override.

    Overrides the FastAPI dependency to use our test database session
    instead of the production database connection.
    """

    def override_get_db():
        # return our test session instead of creating a new one
        try:
            yield test_session
        finally:
            pass

    def override_get_queue():
        # return our mock queue instead of creating a real one
        return mock_sync_queries

    def mock_get_current_user():
        # try to find the mock user in the database first
        user = test_session.query(User).filter(User.id == MOCK_USER_ID).first()
        if user:
            return CurrentUser(
                id=str(user.id),
                email=user.email,
                organization_id=user.organization_id,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
            )
        else:
            raise HTTPException(status_code=401, detail="User not found")

    # override the FastAPI dependency injection
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_queue] = override_get_queue
    app.dependency_overrides[get_current_user] = mock_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    # clean up dependency overrides after test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauthorized_client(test_session, mock_sync_queries):
    """Create a test client without auth override - tests unauthorized access."""

    def override_get_db():
        try:
            yield test_session
        finally:
            pass

    def override_get_queue():
        # return our mock queue instead of creating a real one
        return mock_sync_queries

    # only override database and queue, not auth
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_queue] = override_get_queue

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def mock_sync_queries():
    """provide mock sync queries for tests"""
    # return the mock_sync_queries object created at module level
    mock_queries = MagicMock()
    mock_queries.enqueue = MagicMock(return_value="mock-job-id")
    mock_queries.dequeue = MagicMock(return_value=None)
    return mock_queries


@pytest.fixture(scope="function", autouse=True)
def mock_jwt_settings(mocker: MockerFixture):
    """mock JWT settings globally for all tests"""
    mocker.patch("app.utils.jwt.JWT_SECRET_KEY", TEST_JWT_SECRET_KEY)
    mocker.patch("app.utils.jwt.JWT_ALGORITHM", TEST_JWT_ALGORITHM)


@pytest.fixture(scope="function", autouse=True)
def mock_encryption_secret_key(mocker: MockerFixture):
    """mock encryption secret key and salt globally for all tests"""
    mocker.patch("app.core.config.config.ENCRYPTION_SECRET_KEY", TEST_ENCRYPTION_SECRET_KEY)
    mocker.patch("app.core.config.config.ENCRYPTION_SALT", TEST_ENCRYPTION_SALT)
