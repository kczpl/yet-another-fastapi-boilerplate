from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items import repository
from scripts.seed import DEMO_ITEMS, seed


async def test_seed_creates_the_demo_items_once(db_session: AsyncSession):
    first = await seed(db_session)
    second = await seed(db_session)

    assert (first, second) == (len(DEMO_ITEMS), 0)
    assert await repository.count_items(db_session) == len(DEMO_ITEMS)
