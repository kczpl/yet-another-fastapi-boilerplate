from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.items import crud
from tests.factories.item import ItemFactory


class TestItemCrud:
    async def test_get_item_by_id(self, db_session: AsyncSession):
        item = await ItemFactory.create(name="Findable")

        found = await crud.get_item_by_id(db_session, item.id)

        assert found is not None
        assert found.name == "Findable"

    async def test_set_item_summary(self, db_session: AsyncSession):
        item = await ItemFactory.create(summary=None)

        await crud.set_item_summary(db_session, item, "the summary")

        assert item.summary == "the summary"

    async def test_list_filters_by_status(self, db_session: AsyncSession):
        await ItemFactory.create(status="active")
        await ItemFactory.create(status="archived")

        items, total = await crud.list_items_with_count(db_session, limit=10, offset=0, status="archived")

        assert total == 1
        assert items[0].status == "archived"
