from typing import TypeVar, Any, Type
from sqlalchemy.orm import Query
from math import ceil

from app.models.base.schemas import PaginatedResponse

T = TypeVar("T")
R = TypeVar("R", bound=PaginatedResponse)


def paginate_query(
    query: Query,
    page: int,
    page_size: int,
    result_mapper: callable = None,
    response_class: Type[R] = None,
) -> R | PaginatedResponse[Any]:
    """
    Generic pagination utility for SQLAlchemy queries

    Args:
        query: SQLAlchemy query object
        page: Page number (1-based)
        page_size: Number of items per page
        result_mapper: Optional function to transform query results
        response_class: Specific PaginatedResponse subclass to return

    Returns:
        PaginatedResponse with data and pagination metadata
    """
    # get total count
    total = query.count()

    # calculate pagination values
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size

    # get paginated results
    items = query.offset(offset).limit(page_size).all()

    # apply result mapper if provided
    if result_mapper:
        data = [result_mapper(item) for item in items]
    else:
        data = items

    pagination_data = {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

    if response_class:
        return response_class(**pagination_data)

    return PaginatedResponse(**pagination_data)
