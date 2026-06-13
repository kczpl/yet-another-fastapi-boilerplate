from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent

from app.core.agents import get_model, get_model_settings, get_usage_limits, log_agent_cost
from app.core.config import ai_config
from app.core.logger import log

# Example flat (single-file) agent, colocated with the feature that uses it. The
# whole module is: model constant, output model + validator, the Agent built at
# import time, and one async wrapper. General config lives in app/core/agents.py.
# See .claude/rules/backend/ai-agents.md for the full conventions.

MODEL = ai_config.BEDROCK_MODEL

# instructions= MUST be a static str constant (an f-string kills Bedrock caching).
# Dynamic data goes in the user prompt passed to agent.run().
SUMMARIZER_PROMPT = (
    "You summarize text. Produce a short title, a one-paragraph summary, and 3-5 "
    "keywords. Be faithful to the source — never invent facts not present in it."
)


class TextSummary(BaseModel):
    title: str = Field(max_length=120)
    summary: str
    keywords: list[str]

    @model_validator(mode="after")
    def normalize(self):
        self.title = self.title.strip()
        self.keywords = [k.strip().lower() for k in self.keywords if k.strip()][:5]
        return self


summarizer_agent = Agent(
    get_model(MODEL),
    name="text-summarizer",
    output_type=TextSummary,
    instructions=SUMMARIZER_PROMPT,
    model_settings=get_model_settings(),
    retries=2,
)


async def summarize_text(text: str) -> TextSummary:
    log.debug("text_summarization_started", chars=len(text))
    result = await summarizer_agent.run(text, usage_limits=get_usage_limits())
    log_agent_cost(
        "text_summarization_completed",
        result.usage,
        result.response.model_name or MODEL,
        keywords=len(result.output.keywords),
    )
    return result.output
