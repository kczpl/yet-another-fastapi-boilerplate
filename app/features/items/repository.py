import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items.models import Item

# Repository functions never commit — they flush to materialize IDs/defaults. The
# transaction belongs to the caller (route service commits; Celery auto-commits).


async def create_item(db: AsyncSession, *, name: str, description: str | None = None) -> Item:
    item = Item(name=name, description=description)
    db.add(item)
    await db.flush()
    return item


async def get_item_by_id(db: AsyncSession, item_id: uuid.UUID) -> Item | None:
    result = await db.execute(select(Item).where(Item.id == item_id))
    return result.scalar_one_or_none()


async def list_items_with_count(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Item], int]:
    # A separate count also works when the requested page is past the last row.
    total = await count_items(db)
    stmt = select(Item).order_by(Item.created_at.desc(), Item.id.desc()).limit(limit).offset(offset)
    items = await db.scalars(stmt)
    return list(items), total


async def count_items(db: AsyncSession) -> int:
    return (await db.scalar(select(func.count()).select_from(Item))) or 0


async def set_item_summary(db: AsyncSession, item: Item, summary: str) -> Item:
    item.summary = summary
    await db.flush()
    return item
