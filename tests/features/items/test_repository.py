from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items import repository
from app.utils.time import utc_now
from tests.factories.item import ItemFactory


class TestItemCrud:
    async def test_get_item_by_id(self, db_session: AsyncSession):
        item = await ItemFactory.create(name="Findable")

        found = await repository.get_item_by_id(db_session, item.id)

        assert found is not None
        assert found.name == "Findable"

    async def test_set_item_summary(self, db_session: AsyncSession):
        item = await ItemFactory.create(summary=None)

        await repository.set_item_summary(db_session, item, "the summary")

        assert item.summary == "the summary"

    async def test_list_items_with_count(self, db_session: AsyncSession):
        await ItemFactory.create(name="a")
        await ItemFactory.create(name="b")

        items, total = await repository.list_items_with_count(db_session, limit=10, offset=0)

        assert total == 2
        assert len(items) == 2

    async def test_equal_timestamps_have_stable_order(self, db_session: AsyncSession):
        timestamp = utc_now()
        first = await ItemFactory.create(created_at=timestamp)
        second = await ItemFactory.create(created_at=timestamp)

        page_one, _ = await repository.list_items_with_count(db_session, limit=1, offset=0)
        page_two, _ = await repository.list_items_with_count(db_session, limit=1, offset=1)

        assert [page_one[0].id, page_two[0].id] == sorted([first.id, second.id], reverse=True)

    async def test_repository_does_not_commit(self, db_session: AsyncSession):
        existing = await ItemFactory.create()
        existing_id = existing.id
        await db_session.commit()
        created = await repository.create_item(db_session, name="rolled back")
        created_id = created.id

        await db_session.rollback()

        assert await repository.get_item_by_id(db_session, created_id) is None
        assert await repository.get_item_by_id(db_session, existing_id) is not None

    async def test_database_generates_uuid7_and_defaults(self, db_session: AsyncSession):
        row = (
            await db_session.execute(
                text("INSERT INTO public.items (name) VALUES ('raw') RETURNING id, status, created_at")
            )
        ).one()

        assert row.id.version == 7
        assert row.status == "active"
        assert row.created_at.tzinfo is not None
