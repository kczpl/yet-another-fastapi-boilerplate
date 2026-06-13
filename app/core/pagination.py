from dataclasses import dataclass

from fastapi import Query


@dataclass
class Pagination:
    page: int
    page_size: int


def pagination_params(default_page_size: int = 10):
    # Factory so endpoints keep their own default page_size — changing a default
    # silently changes API behaviour for clients that omit the param.
    def dependency(
        page: int = Query(1, ge=1),
        page_size: int = Query(default_page_size, ge=1, le=100),
    ) -> Pagination:
        return Pagination(page=page, page_size=page_size)

    return dependency
