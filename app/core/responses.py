from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    message: str | None = None
    data: T | None = None


# Map short keys → i18n message keys. Routes/services reference MESSAGES["..."]
# so the wire format stays consistent and translatable.
MESSAGES = {
    "success": "api.general.success",
    "created": "api.general.created",
    "deleted": "api.general.deleted",
}
