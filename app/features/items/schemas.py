import uuid
from datetime import datetime
from typing import Annotated

from pydantic import MISSING, BaseModel, ConfigDict, StringConstraints

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
# The summarizer sends the description to the model. The limit caps the input of one request.
ItemDescription = Annotated[str, StringConstraints(max_length=10_000)]


class ItemCreate(BaseModel):
    name: ItemName
    description: ItemDescription | None = None


class ItemUpdate(BaseModel):
    # MISSING marks a field that the request does not send. model_dump() leaves it out.
    name: ItemName | MISSING = MISSING
    description: ItemDescription | MISSING | None = MISSING


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    summary: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int
