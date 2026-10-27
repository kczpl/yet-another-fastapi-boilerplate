from typing import Literal, TypedDict
from uuid import UUID

from app.core.logger import log
from app.features.items import repository
from app.features.items.agents.summarizer import summarize_text
from app.services.base import Service


class SummaryResult(TypedDict):
    item_id: UUID
    status: Literal["summarized", "skipped"]


class SummarizeItemService(Service):
    # Worker service for `summarize_item_task`. session_scope() in run_service() commits
    # on success, so this service does not commit.
    async def call(self, item_id: UUID) -> SummaryResult:
        item = await repository.get_item_by_id(self.db, item_id)
        # Idempotent: re-delivery / retry after a worker crash must converge, not
        # re-summarize. Skip if there's nothing to do or it's already done.
        if item is None or not item.description or item.summary is not None:
            log.info("summarize_item_skipped", item_id=str(item_id))
            return {"item_id": item_id, "status": "skipped"}

        result = await summarize_text(item.description)
        await repository.set_item_summary(self.db, item, result.summary)
        return {"item_id": item_id, "status": "summarized"}
