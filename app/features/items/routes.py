from fastapi import APIRouter, Depends, status

from app.core.db import AsyncDb
from app.core.pagination import Pagination, pagination_params
from app.core.responses import MESSAGES, APIResponse
from app.features.items.dependencies import ValidItem
from app.features.items.schemas import ItemCreate, ItemListResponse, ItemResponse
from app.features.items.services.create import CreateItemService
from app.features.items.services.list import ListItemsService

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
    pagination: Pagination = Depends(pagination_params()),
) -> dict:
    return {"data": await ListItemsService(db).call(page=pagination.page, page_size=pagination.page_size)}


@router.get("/items/{item_id}", response_model=APIResponse[ItemResponse])
async def get_item(item: ValidItem) -> dict:
    # valid_item_id (dependency) already loaded the item or raised 404.
    return {"data": item}
