from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
