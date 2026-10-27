import pytest

pytest.importorskip("pydantic_ai")

from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from app.features.items.agents.summarizer import TextSummary, get_summarizer, summarize_text


@pytest.fixture
def test_model():
    # Replace the Bedrock model factory. The real provider loads AWS credentials.
    model = TestModel(custom_output_args={"title": " Title ", "summary": "s", "keywords": ["Alpha"]})
    get_summarizer.cache_clear()
    with patch("app.features.items.agents.summarizer.get_model", return_value=model):
        yield model
    get_summarizer.cache_clear()


def test_text_summary_normalizes_title_and_keywords():
    # Output-model unit test: exercises the @model_validator without a model call.
    summary = TextSummary(title="  Title ", summary="s", keywords=[" Alpha", "", "beta ", "c", "d", "e", "f"])

    assert summary.title == "Title"
    assert summary.keywords == ["alpha", "beta", "c", "d", "e"]


async def test_summarize_text_returns_normalized_output(test_model: TestModel):
    summary = await summarize_text("long text")

    assert summary == TextSummary(title="Title", summary="s", keywords=["alpha"])
