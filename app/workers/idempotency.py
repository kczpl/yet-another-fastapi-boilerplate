import uuid

from app.core.db.async_ import async_redis

DELIVERY_MARKER_TTL_SECONDS = 24 * 60 * 60


def new_dedup_key() -> str:
    return str(uuid.uuid4())


def _marker(kind: str, dedup_key: str) -> str:
    return f"task_delivered:{kind}:{dedup_key}"


async def is_already_delivered(kind: str, dedup_key: str) -> bool:
    return bool(await async_redis.exists(_marker(kind, dedup_key)))


async def mark_delivered(kind: str, dedup_key: str) -> None:
    await async_redis.set(_marker(kind, dedup_key), "1", ex=DELIVERY_MARKER_TTL_SECONDS)
