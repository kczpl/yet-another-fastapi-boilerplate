import pytest

pytest.importorskip("pydantic_ai")

from app.features.items.agents.summarizer import TextSummary


def test_text_summary_normalizes_title_and_keywords():
    # Output-model unit test: exercises the @model_validator without a model call.
    summary = TextSummary(title="  Title ", summary="s", keywords=[" Alpha", "", "beta ", "c", "d", "e", "f"])

    assert summary.title == "Title"
    assert summary.keywords == ["alpha", "beta", "c", "d", "e"]
