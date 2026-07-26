from typing import Any

from app.features.items.schemas import ItemResponse
from app.repositories.items.models import Item


def serialize_item(item: Item) -> dict[str, Any]:
    # Single source of truth: ItemResponse fields. Services return plain dicts;
    # response_model validates them again at the API boundary.
    return ItemResponse.model_validate(item, from_attributes=True).model_dump()
