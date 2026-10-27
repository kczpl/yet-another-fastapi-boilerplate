from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items.services.update import UpdateItemService
from tests.factories.item import ItemFactory


class TestUpdateItemService:
    async def test_update_sets_updated_at(self, db_session: AsyncSession):
        item = await ItemFactory.create()
        created_at = item.updated_at

        await UpdateItemService(db=db_session).call(item, name="Renamed")

        assert item.updated_at > created_at

    async def test_new_description_clears_summary(self, db_session: AsyncSession):
        item = await ItemFactory.create(description="Old", summary="Old summary")

        await UpdateItemService(db=db_session).call(item, description="New")

        assert item.summary is None

    async def test_same_description_keeps_summary(self, db_session: AsyncSession):
        item = await ItemFactory.create(description="Same", summary="Summary")

        await UpdateItemService(db=db_session).call(item, name="Renamed", description="Same")

        assert item.summary == "Summary"
