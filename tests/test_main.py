from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from structlog.testing import capture_logs

from app.core.db import get_db
from app.main import api, app


async def test_ready_answers_ok_when_the_database_answers(client: AsyncClient):
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.text == "OK"


async def test_ready_answers_503_without_the_database():
    # No server listens on port 1, so the connection fails at once.
    unreachable = create_async_engine("postgresql+psycopg://app:app@127.0.0.1:1/app")

    async def unreachable_db() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(unreachable) as session:
            yield session

    api.dependency_overrides[get_db] = unreachable_db
    try:
        with capture_logs() as logs:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/ready")
    finally:
        api.dependency_overrides.clear()
        await unreachable.dispose()

    assert response.status_code == 503
    assert [entry["event"] for entry in logs] == ["readiness_check_failed"]
