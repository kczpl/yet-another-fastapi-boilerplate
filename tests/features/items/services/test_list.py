from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items.services.list import ListItemsService
from tests.factories.item import ItemFactory


class TestListItemsService:
    async def test_list_paginates_and_counts(self, db_session: AsyncSession):
        for _ in range(3):
            await ItemFactory.create()

        result = await ListItemsService(db=db_session).call(page=1, page_size=2)

        assert result["total_count"] == 3
        assert result["total_pages"] == 2
        assert len(result["items"]) == 2

    async def test_list_empty(self, db_session: AsyncSession):
        result = await ListItemsService(db=db_session).call(page=1, page_size=10)

        assert result["total_count"] == 0
        assert result["total_pages"] == 0
        assert result["items"] == []

    async def test_page_past_end_keeps_total_count(self, db_session: AsyncSession):
        await ItemFactory.create()

        result = await ListItemsService(db=db_session).call(page=2, page_size=10)

        assert result["items"] == []
        assert result["total_count"] == 1
        assert result["total_pages"] == 1
