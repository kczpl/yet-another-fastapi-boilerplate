from functools import lru_cache

import sentry_sdk
from pydantic_ai import UsageLimits
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider
from pydantic_ai.usage import RunUsage

from app.core.config import ai_config, aws_config
from app.core.logger import log

# General pydantic-ai / Bedrock configuration shared by every agent. Individual
# agents live next to the feature that uses them (e.g. app/features/items/agents/).
# See .claude/rules/backend/ai-agents.md.


@lru_cache(maxsize=1)
def _get_bedrock_provider() -> BedrockProvider:
    # lru_cache keeps one provider per process and is fork-safe (built lazily on
    # first use, after the worker has forked) — never construct one at import time.
    return BedrockProvider(
        region_name=ai_config.BEDROCK_REGION,
        aws_access_key_id=aws_config.AWS_ACCESS_KEY,
        aws_secret_access_key=aws_config.AWS_SECRET_KEY,
    )


@lru_cache(maxsize=8)
def get_model(model_name: str | None = None) -> BedrockConverseModel:
    return BedrockConverseModel(
        model_name=model_name or ai_config.BEDROCK_MODEL,
        provider=_get_bedrock_provider(),
    )


def get_model_settings() -> BedrockModelSettings:
    return BedrockModelSettings(
        max_tokens=ai_config.AI_MAX_TOKENS,
        bedrock_cache_instructions="1h",
        bedrock_cache_tool_definitions="1h",
    )


def get_usage_limits() -> UsageLimits:
    # Pass as usage_limits= to every agent.run().
    return UsageLimits(
        request_limit=ai_config.AI_REQUEST_LIMIT,
        total_tokens_limit=ai_config.AI_REQUEST_TOKEN_LIMIT,
    )


def log_agent_cost(event: str, usage: RunUsage, model_name: str, **extra: object) -> None:
    # Call after every agent.run() so there is no untracked spend. USD pricing is
    # best-effort via genai_prices (optional dependency); token counts always log.
    input_cost_usd = output_cost_usd = total_cost_usd = None
    try:
        from genai_prices import calc_price

        price = calc_price(usage, model_name, provider_id="aws")
        input_cost_usd = float(round(price.input_price, 6))
        output_cost_usd = float(round(price.output_price, 6))
        total_cost_usd = float(round(price.total_price, 6))
    except Exception:
        pass

    log.info(
        event,
        model=model_name,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        requests=usage.requests,
        total_cost_usd=total_cost_usd,
        **extra,
    )
    _emit_sentry_ai_context(event, model_name, input_cost_usd, output_cost_usd, total_cost_usd)


def _emit_sentry_ai_context(event, model_name, input_cost_usd, output_cost_usd, total_cost_usd) -> None:
    if not sentry_sdk.is_initialized():
        return
    sentry_sdk.set_tag("ai_agent", event)
    sentry_sdk.set_tag("ai_model", model_name)
    span = sentry_sdk.get_current_span()
    if span is not None and total_cost_usd is not None:
        span.set_data("gen_ai.cost.input_tokens", input_cost_usd)
        span.set_data("gen_ai.cost.output_tokens", output_cost_usd)
        span.set_data("gen_ai.cost.total_tokens", total_cost_usd)
