from fastapi import APIRouter, status

from app.core.responses import MESSAGES, APIResponse
from app.features.items.dependencies import ValidItem
from app.workers.enqueue import enqueue_summarize_item

router = APIRouter(tags=["items"])


@router.post(
    "/items/{item_id}/summarize",
    response_model=APIResponse[None],
    status_code=status.HTTP_202_ACCEPTED,
)
def summarize_item(item: ValidItem) -> dict:
    # Offload the LLM work to the `heavy` queue; the endpoint returns immediately.
    enqueue_summarize_item(str(item.id))
    return {"message": MESSAGES["success"]}
