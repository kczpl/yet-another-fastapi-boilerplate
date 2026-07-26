from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items.service.list import ListItemsService
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
