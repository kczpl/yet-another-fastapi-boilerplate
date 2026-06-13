from fastapi import APIRouter, Depends, status

from app.core.pagination import Pagination, pagination_params
from app.core.responses import MESSAGES, APIResponse
from app.features.items.schemas import ItemCreate, ItemListResponse, ItemResponse
from app.features.items.service.create import CreateItemService
from app.features.items.service.helpers import serialize_item
from app.features.items.service.list import ListItemsService
from app.repositories.items.dependencies import ValidItem
from app.workers.queue import enqueue_summarize_item

# No prefix on the router — use full paths in every decorator (keeps REST paths
# explicit and greppable). Aggregated under /api/v1 in app/api/__init__.py.
router = APIRouter(tags=["items"])


@router.post("/items", response_model=APIResponse[ItemResponse], status_code=status.HTTP_201_CREATED)
async def create_item(body: ItemCreate, service: CreateItemService = Depends()) -> dict:
    return await service.call(name=body.name, description=body.description)


@router.get("/items", response_model=APIResponse[ItemListResponse])
async def list_items(
    pagination: Pagination = Depends(pagination_params()),
    service: ListItemsService = Depends(),
) -> dict:
    return await service.call(page=pagination.page, page_size=pagination.page_size)


@router.get("/items/{item_id}", response_model=APIResponse[ItemResponse])
async def get_item(item: ValidItem) -> dict:
    # valid_item_id (dependency) already loaded the item or raised 404.
    return {"data": serialize_item(item)}


@router.post(
    "/items/{item_id}/summarize",
    response_model=APIResponse[None],
    status_code=status.HTTP_202_ACCEPTED,
)
async def summarize_item(item: ValidItem) -> dict:
    # Offload the LLM work to the `ai` queue; the endpoint returns immediately.
    enqueue_summarize_item(str(item.id))
    return {"message": MESSAGES["success"]}
