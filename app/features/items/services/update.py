from typing import Unpack

from app.features.items import repository
from app.features.items.models import Item
from app.features.items.repository import ItemChanges
from app.services.base import Service


class UpdateItemService(Service):
    async def call(self, item: Item, **changes: Unpack[ItemChanges]) -> Item:
        # A new description makes the old summary stale.
        if changes.get("description", item.description) != item.description:
            changes["summary"] = None
        await repository.update_item(self.db, item, **changes)
        await self.db.commit()
        return item
