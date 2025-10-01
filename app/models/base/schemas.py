from typing import Generic, TypeVar, List, Any
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from fastapi.encoders import jsonable_encoder

T = TypeVar("T")


def datetime_to_gmt_str(dt: datetime) -> str:
    """Convert datetime to standard GMT string format with timezone."""
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


class Base(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @field_serializer("*", mode="wrap", check_fields=False)
    def serialize_datetime(self, value: Any, handler, info) -> Any:
        """Serialize datetime fields to GMT string format."""
        result = handler(value)
        if isinstance(result, datetime):
            return datetime_to_gmt_str(result)
        return result

    def serializable_dict(self, **kwargs):
        """Return a dict which contains only serializable fields."""
        default_dict = self.model_dump()
        return jsonable_encoder(default_dict)


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
