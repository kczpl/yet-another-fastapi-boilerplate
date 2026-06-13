---
paths:
  - "app/core/agents.py"
  - "app/**/agents/**"
---

# AI Agents (Pydantic AI + Bedrock)

Project conventions for AI agents. For the generic pydantic-ai API, see the pydantic-ai docs.

## Principles

- One agent = one async wrapper (`summarize_text`, `classify_document`, ...). The wrapper does four things: build prompt → `agent.run()` → `log_agent_cost(...)` → return `result.output`.
- Static `instructions=` so the Bedrock cache hits; dynamic data goes in the user prompt or via `deps`.
- `log_agent_cost(...)` after every `agent.run()`. No untracked spend.
- Validators degrade gracefully — on the final retry, flag `requires_review` / clamp `confidence` rather than crashing (when the output model has those fields).
- Real-LLM tests are env-gated; pure validator/output tests run in CI.

## File layout

General config lives in `app/core/agents.py`. **Each agent is colocated with the feature that uses it**, under `app/features/<domain>/agents/`.

**Flat** (single file) — model constant, output model, `Agent(...)`, async wrapper. Example: `app/features/items/agents/summarizer.py`.

**Sub-package** (when you add tools / validators):

```
app/features/<domain>/agents/my_agent/
├── __init__.py     # re-exports + side-effect imports (mandatory)
├── agent.py        # Agent(...) + async wrapper
├── prompt.py       # segment constants joined into one system prompt
├── outputs.py      # Pydantic models with @model_validator(mode="after")
├── tools.py        # @agent.tool
└── validators.py   # @agent.output_validator + _check_* helpers
```

`@agent.tool` and `@agent.output_validator` only register if the module is imported. `__init__.py` must do `from . import tools as _tools  # noqa: F401` (and the validators module). Without these, the agent silently loses them.

## Central config — `app/core/agents.py`

| Helper | Use |
|---|---|
| `get_model(name=None)` | Cached `BedrockConverseModel` factory (fork-safe `@lru_cache`). Never construct one directly. |
| `get_model_settings()` | `BedrockModelSettings` with `max_tokens` + `bedrock_cache_instructions/tool_definitions="1h"`. |
| `get_usage_limits()` | Pass as `usage_limits=` to every `agent.run()`. |
| `log_agent_cost(event, usage, model, **extra)` | Call after every run. Logs tokens (+ best-effort USD via `genai_prices`) and tags the Sentry span. |

Model ids are Bedrock inference profiles set in `AIConfig` (`BEDROCK_MODEL`, `BEDROCK_MODEL_HAIKU`) — account- and region-specific. Pick the cheapest tier that passes your eval; only move up where a cheaper model regresses.

## Canonical agent

```python
MODEL = ai_config.BEDROCK_MODEL

agent = Agent(
    get_model(MODEL),
    name="text-summarizer",
    output_type=TextSummary,           # or PromptedOutput(TextSummary)
    instructions=SUMMARIZER_PROMPT,    # STATIC — never an f-string
    model_settings=get_model_settings(),
    retries=2,                         # int sets both tool+output budgets
)

async def summarize_text(text: str) -> TextSummary:
    result = await agent.run(text, usage_limits=get_usage_limits())
    log_agent_cost("text_summarization_completed", result.usage, result.response.model_name or MODEL)
    return result.output
```

Required: `Agent` built at module import; `name=` set; `instructions=` is a `str` constant; `retries=` explicit; wrapper returns the typed output.

Variations: `deps_type=` for per-run state; `BinaryContent(data=bytes, media_type=...)` for image/PDF input; a callable `model_settings=(ctx) -> BedrockModelSettings` to vary per attempt; extended thinking via `bedrock_additional_model_requests_fields={"thinking": {"type": "enabled", "budget_tokens": N}}`.

## Caching

Configured only through `BedrockModelSettings` cache flags — no manual `cache_control`.

- `instructions=` is a constant — any per-request interpolation breaks the cache.
- Dynamic data goes in the user prompt (or a tool reading `ctx.deps`).
- Tool schemas must be stable across calls.

## Outputs & Validators

- Plain Pydantic models, modern types (`str | None`, `list[Item]`).
- `@model_validator(mode="after")` for normalization (strip, derive computed fields).
- For human-review flows, add `requires_review: bool` / `confidence: float | None` and flip them on the final retry.

```python
@agent.output_validator
def _validate(ctx, output):
    errors = [e for e in (_check_a(output), _check_b(output)) if e]
    if not errors:
        return output
    if ctx.retry >= _FINAL_RETRY:        # mirror the agent's retries=
        output.requires_review = True
        return output
    raise ModelRetry("Validator failed:\n- " + "\n- ".join(errors))
```

- `_check_*` returns `None` or a multi-line error string with **corrective instructions** (the model reads it on retry); keep them top-level so tests import them.
- Aggregate all errors into one `ModelRetry`.

## Tools

- `@agent.tool` when the tool needs `RunContext[Deps]`; `@agent.tool_plain` otherwise.
- The **docstring is the model-visible tool description** — write it as an instruction ("call this whenever you need to ...").
- Register via side-effect import in `__init__.py`.

## Service integration

Direct call — no abstraction:

```python
result = await summarize_text(item.description)
```

LLM-bound work runs on the `heavy` Celery queue (`QUEUE_HEAVY`) — offload it from request handlers (see `background.md`).

## Errors

| Exception | Where | Handling |
|---|---|---|
| `UsageLimitExceeded` | `agent.run()` | Re-raise as a domain error (e.g. 422). |
| `UnexpectedModelBehavior` | `agent.run()` | Re-raise as a domain error (500). |
| `ModelRetry` | inside tool/validator | **Never catch.** Must propagate to the agent loop. |
| Bedrock/AWS connection | `agent.run()` | Celery `autoretry_for=(...)` at the task layer. |

Don't wrap `agent.run()` in `except Exception` — handle exactly the declared exceptions.

## Don'ts

- `instructions=` is never an f-string — kills caching.
- Don't catch `ModelRetry` — silently disables the validator.
- Don't construct `BedrockProvider` / `BedrockConverseModel` directly — use `get_model()` (`@lru_cache`, fork-safe).
- Don't omit `__init__.py` side-effect imports — decorators only fire on import.
- Don't run real-LLM tests in CI — env-gate them.
