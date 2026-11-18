import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal, engine
from app.core.logger import log, setup_logging
from app.features.items import repository
from app.features.items.services.create import CreateItemService

# Demo rows for a manual check of the local app: `just seed`. Safe to run again.
DEMO_ITEMS = (
    ("Welcome", "A first example item."),
    ("Quarterly report", "Revenue grew in the third quarter. Costs stayed flat."),
    ("No description", None),
)


async def seed(db: AsyncSession) -> int:
    if await repository.count_items(db):
        return 0
    for name, description in DEMO_ITEMS:
        await CreateItemService(db).call(name=name, description=description)
    return len(DEMO_ITEMS)


async def main() -> None:
    try:
        async with SessionLocal() as db:
            created = await seed(db)
    finally:
        await engine.dispose()
    log.info("seed_completed", created_rows=created)


if __name__ == "__main__":
    setup_logging(app="seed")
    asyncio.run(main())
