import math
from typing import TypedDict

from app.features.items import repository
from app.features.items.models import Item
from app.services.base import Service


class ItemPage(TypedDict):
    items: list[Item]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class ListItemsService(Service):
    async def call(self, *, page: int, page_size: int) -> ItemPage:
        items, total_count = await repository.list_items_with_count(
            self.db,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": math.ceil(total_count / page_size),
        }
