from app.features.items import repository
from app.features.items.models import Item
from app.services.base import Service


class CreateItemService(Service):
    async def call(self, *, name: str, description: str | None = None) -> Item:
        item = await repository.create_item(self.db, name=name, description=description)
        await self.db.commit()
        return item
