from typing import Any

from app.repositories.items.models import Item


def serialize_item(item: Item) -> dict[str, Any]:
    # Services return plain dicts; Pydantic validates them at the API layer via
    # response_model. Build the dict explicitly instead of relying on from_attributes.
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "summary": item.summary,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
