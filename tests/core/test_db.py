import pytest

from app.core.db import to_psycopg_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://app:app@db/app", "postgresql+psycopg://app:app@db/app"),
        ("postgresql+asyncpg://app:app@db/app", "postgresql+psycopg://app:app@db/app"),
        ("postgresql+psycopg://app:app@db/app", "postgresql+psycopg://app:app@db/app"),
    ],
)
def test_to_psycopg_url(url: str, expected: str):
    assert to_psycopg_url(url) == expected
