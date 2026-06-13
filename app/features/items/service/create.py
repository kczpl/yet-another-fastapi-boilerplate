from typing import Any

from app.core.responses import MESSAGES
from app.features.items.service.helpers import serialize_item
from app.repositories.items import crud
from app.services.base import Service


class CreateItemService(Service):
    async def call(self, *, name: str, description: str | None = None) -> dict[str, Any]:
        item = await crud.create_item(self.db, name=name, description=description)
        await self.db.commit()
        return {"message": MESSAGES["created"], "data": serialize_item(item)}
