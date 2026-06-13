import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.items.models import Item

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
    status: str | None = None,
) -> tuple[list[Item], int]:
    # Window function gets the total count in the same query — no second round-trip.
    total_count_expr = func.count().over().label("total_count")
    stmt = select(Item, total_count_expr).order_by(Item.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(Item.status == status)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return [], 0
    return [row[0] for row in rows], rows[0][1]


async def set_item_summary(db: AsyncSession, item: Item, summary: str) -> Item:
    item.summary = summary
    await db.flush()
    return item
