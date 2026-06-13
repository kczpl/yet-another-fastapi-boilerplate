from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items.service.create import CreateItemService
from app.repositories.items.models import Item


class TestCreateItemService:
    async def test_create_item_persists(self, db_session: AsyncSession):
        service = CreateItemService(db=db_session)

        result = await service.call(name="Widget", description="A useful widget")

        assert result["data"]["name"] == "Widget"
        assert result["data"]["status"] == "active"

        item = (await db_session.execute(select(Item).where(Item.name == "Widget"))).scalar_one()
        assert item.description == "A useful widget"
        assert item.summary is None

    async def test_create_item_without_description(self, db_session: AsyncSession):
        service = CreateItemService(db=db_session)

        result = await service.call(name="Bare")

        assert result["data"]["description"] is None
