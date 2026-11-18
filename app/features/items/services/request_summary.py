from app.features.items.models import Item
from app.services.base import Service
from app.workers.enqueue import enqueue_summarize_item


class RequestSummaryService(Service):
    async def call(self, item: Item) -> None:
        # Publish only after the commit, so the worker reads the committed state.
        # The commit also returns the request connection before the broker call.
        await self.db.commit()
        await enqueue_summarize_item(item.id)
