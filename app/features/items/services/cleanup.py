from app.core.logger import log
from app.features.items import repository
from app.services.base import Service


class CleanupItemsService(Service):
    # Example periodic (cron) task service. Idempotent — beat fires it again next
    # interval, so the body just reports current state. Replace with real work.
    async def call(self) -> dict:
        total = await repository.count_items(self.db)
        log.info("cleanup_items_ran", total_items=total)
        return {"total_items": total}
