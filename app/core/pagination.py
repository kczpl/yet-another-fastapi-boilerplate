from pydantic import BaseModel, Field


class Pagination(BaseModel):
    # Use as `Annotated[Pagination, Query()]`. For another default page_size, subclass it:
    # a changed default changes the API for clients that omit the parameter.
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
