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
    # the final write. The early commit below only ends the read transaction.
    async def call(self, item_id: UUID) -> SummaryResult:
        item = await repository.get_item_by_id(self.db, item_id)
        # Idempotent: a redelivered task skips an item that is already done.
        if item is None or not item.description or item.summary is not None:
            return _skipped(item_id)

        description = item.description
        # An open transaction holds a pool connection during the whole model call.
        await self.db.commit()
        result = await summarize_text(description)

        item = await repository.get_item_for_update(self.db, item_id)
        # The item can change during the model call. Keep the newer state.
        if item is None or item.description != description or item.summary is not None:
            return _skipped(item_id)
        await repository.set_item_summary(self.db, item, result.summary)
        return {"item_id": item_id, "status": "summarized"}


def _skipped(item_id: UUID) -> SummaryResult:
    log.info("summarize_item_skipped", item_id=str(item_id))
    return {"item_id": item_id, "status": "skipped"}
