from fastapi import APIRouter, status

from app.core.db import AsyncDb
from app.core.responses import MESSAGES, APIResponse
from app.features.items.dependencies import ValidItem
from app.features.items.services.request_summary import RequestSummaryService

router = APIRouter(tags=["items"])


@router.post(
    "/items/{item_id}/summarize",
    response_model=APIResponse[None],
    status_code=status.HTTP_202_ACCEPTED,
)
async def summarize_item(item: ValidItem, db: AsyncDb) -> dict:
    # The LLM work runs on the `heavy` queue; the endpoint returns at once.
    await RequestSummaryService(db).call(item)
    return {"message": MESSAGES["success"]}
