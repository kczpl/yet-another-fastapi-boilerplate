from app.features.items import repository
from app.features.items.models import Item
from app.services.base import Service


class DeleteItemService(Service):
    async def call(self, item: Item) -> None:
        await repository.delete_item(self.db, item)
        await self.db.commit()
