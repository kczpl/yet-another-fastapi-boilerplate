from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_expired(expires_at: datetime) -> bool:
    return utc_now() > expires_at
