import pytest

pytest.importorskip("pydantic_ai")

from unittest.mock import patch
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.items.agents.summarizer import TextSummary
from app.features.items.services.summarize import SummarizeItemService
from tests.factories.item import ItemFactory

SUMMARY = TextSummary(title="Title", summary="A short summary.", keywords=["alpha"])


class TestSummarizeItemService:
    # The tests patch the async model wrapper, so no model is called.
    @patch("app.features.items.services.summarize.summarize_text", return_value=SUMMARY)
    async def test_summarize_stores_summary(self, mock_summarize, db_session: AsyncSession):
        item = await ItemFactory.create(description="long text", summary=None)

        result = await SummarizeItemService(db=db_session).call(item.id)

        assert result == {"item_id": item.id, "status": "summarized"}
        assert item.summary == "A short summary."
        mock_summarize.assert_awaited_once_with("long text")

    @patch("app.features.items.services.summarize.summarize_text")
    async def test_summarize_skips_already_summarized_item(self, mock_summarize, db_session: AsyncSession):
        item = await ItemFactory.create(summary="already done")

        result = await SummarizeItemService(db=db_session).call(item.id)

        assert result["status"] == "skipped"
        assert item.summary == "already done"
        mock_summarize.assert_not_called()

    @patch("app.features.items.services.summarize.summarize_text")
    async def test_summarize_skips_missing_item(self, mock_summarize, db_session: AsyncSession):
        result = await SummarizeItemService(db=db_session).call(UUID(int=0))

        assert result["status"] == "skipped"
        mock_summarize.assert_not_called()
