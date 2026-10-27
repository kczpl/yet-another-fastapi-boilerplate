from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.db import AsyncDb
from app.core.pagination import Pagination, pagination_params
from app.core.responses import MESSAGES, APIResponse
from app.features.items.dependencies import ValidItem
from app.features.items.schemas import ItemCreate, ItemListResponse, ItemResponse, ItemUpdate
from app.features.items.services.create import CreateItemService
from app.features.items.services.delete import DeleteItemService
from app.features.items.services.list import ListItemsService
from app.features.items.services.update import UpdateItemService

# No prefix on the router — use full paths in every decorator (keeps REST paths
# explicit and greppable). Aggregated under /api/v1 in app/api/__init__.py.
router = APIRouter(tags=["items"])


@router.post("/items", response_model=APIResponse[ItemResponse], status_code=status.HTTP_201_CREATED)
async def create_item(body: ItemCreate, db: AsyncDb) -> dict:
    item = await CreateItemService(db).call(name=body.name, description=body.description)
    return {"message": MESSAGES["created"], "data": item}


@router.get("/items", response_model=APIResponse[ItemListResponse])
async def list_items(
    db: AsyncDb,
    pagination: Annotated[Pagination, Depends(pagination_params())],
) -> dict:
    return {"data": await ListItemsService(db).call(page=pagination.page, page_size=pagination.page_size)}


@router.get("/items/{item_id}", response_model=APIResponse[ItemResponse])
async def get_item(item: ValidItem) -> dict:
    # valid_item_id (dependency) already loaded the item or raised 404.
    return {"data": item}


@router.patch("/items/{item_id}", response_model=APIResponse[ItemResponse])
async def update_item(item: ValidItem, body: ItemUpdate, db: AsyncDb) -> dict:
    # model_dump() leaves out the MISSING fields, so only the sent fields change.
    return {"data": await UpdateItemService(db).call(item, **body.model_dump())}


@router.delete("/items/{item_id}", response_model=APIResponse[None])
async def delete_item(item: ValidItem, db: AsyncDb) -> dict:
    await DeleteItemService(db).call(item)
    return {"message": MESSAGES["deleted"]}
