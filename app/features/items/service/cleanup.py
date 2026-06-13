from app.core.logger import log
from app.repositories.items import crud
from app.services.base import Service


class CleanupItemsService(Service):
    # Example periodic (cron) task service. Idempotent — beat fires it again next
    # interval, so the body just reports current state. Replace with real work.
    async def call(self) -> dict:
        _, total = await crud.list_items_with_count(self.db, limit=1, offset=0)
        log.info("cleanup_items_ran", total_items=total)
        return {"total_items": total}
