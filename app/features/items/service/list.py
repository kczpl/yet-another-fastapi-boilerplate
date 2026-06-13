import math
from typing import Any

from app.features.items.service.helpers import serialize_item
from app.repositories.items import crud
from app.services.base import Service


class ListItemsService(Service):
    async def call(self, *, page: int, page_size: int, status: str | None = None) -> dict[str, Any]:
        items, total_count = await crud.list_items_with_count(
            self.db,
            limit=page_size,
            offset=(page - 1) * page_size,
            status=status,
        )
        return {
            "data": {
                "items": [serialize_item(item) for item in items],
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": math.ceil(total_count / page_size) if total_count > 0 else 0,
            }
        }
