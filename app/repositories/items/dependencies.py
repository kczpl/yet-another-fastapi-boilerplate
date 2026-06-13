from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.db import AsyncDb
from app.core.exceptions import raise_not_found
from app.repositories.items import crud
from app.repositories.items.models import Item


async def valid_item_id(item_id: UUID, db: AsyncDb) -> Item:
    # Dependency-as-validation: every route with {item_id} reuses this to load the
    # item and 404 if missing — no repeated existence checks in each endpoint.
    item = await crud.get_item_by_id(db, item_id)
    if item is None:
        raise_not_found("item_not_found")
    return item


ValidItem = Annotated[Item, Depends(valid_item_id)]
