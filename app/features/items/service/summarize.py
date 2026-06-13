from uuid import UUID

from app.core.logger import log
from app.features.items.agents.summarizer import summarize_text
from app.repositories.items import crud
from app.services.base import Service


class SummarizeItemService(Service):
    # Background task service (runs via Celery `summarize_item_task`). Same shape as
    # route-facing services: short call() orchestrator + private steps. async_db_session
    # commits on success, so this service does not commit itself.
    async def call(self, item_id: str) -> dict:
        item = await crud.get_item_by_id(self.db, UUID(item_id))
        # Idempotent: re-delivery / retry after a worker crash must converge, not
        # re-summarize. Skip if there's nothing to do or it's already done.
        if item is None or not item.description or item.summary is not None:
            log.info("summarize_item_skipped", item_id=item_id)
            return {"status": "skipped", "item_id": item_id}

        result = await summarize_text(item.description)
        await crud.set_item_summary(self.db, item, result.summary)
        return {"status": "summarized", "item_id": item_id}
