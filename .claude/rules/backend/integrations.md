---
paths:
  - "app/integrations/**/*.py"
  - "app/features/**/service/**/*.py"
  - "app/workers/**/*.py"
---

# Integrations

External services live in `app/integrations/<service>/`. Keep each integration behind a thin client/function module so feature code depends on your wrapper, not the vendor SDK.

## General Principles

- **Config-driven** — read endpoints, regions, keys from `app/core/config.py` (domain-split `BaseSettings`). Never hardcode URLs, ARNs, regions, or secrets.
- **Async I/O** — prefer `httpx.AsyncClient` over `requests`. For a sync-only SDK, wrap calls in `asyncio.to_thread(...)` and expose an `_async` helper.
- **Fork safety** — never create network clients (boto3, httpx, redis) at module import time. Workers fork after import and children inherit broken sockets. Use an `@lru_cache` factory or instantiate at the call site (the cache is built lazily, after fork).
- **Don't bend code to an integration** — tracking/telemetry is fire-and-forget; never branch business logic on whether an event was sent.

```python
@lru_cache(maxsize=1)
def get_some_client() -> SomeClient:
    return SomeClient(api_key=integrations_config.SOME_API_KEY)
```

## Sentry

Error tracking + tracing. Init at module load — `app/main.py` (API) and `app/workers/celery.py` (workers + beat). 5xx errors are auto-captured by the Starlette / FastAPI / Celery integrations. Only initialized in `staging`/`production` with a `SENTRY_DSN` set.

- PII scrubbing in `_scrub_event` (`app/integrations/sentry/client.py`) is keyword-based and best-effort. Don't log secrets, tokens, or raw request bodies via structlog — oddly-named fields slip through.
- `send_default_pii=False` and `include_local_variables=False` by default. The pydantic-ai integration is added when AI extras are installed; enabling prompt capture (`include_prompts=True` + `send_default_pii=True`) sends model I/O to Sentry — opt in deliberately.
- `CeleryIntegration(monitor_beat_tasks=True)` turns each beat entry into a Sentry Cron monitor.

## AWS Bedrock (AI)

The AI agents use AWS Bedrock via pydantic-ai (see `ai-agents.md`).

- Credentials come from `AWSConfig` (`AWS_ACCESS_KEY` / `AWS_SECRET_KEY` / region) or the default boto3 chain — read them in the cached `BedrockProvider` factory in `app/core/agents.py`, never hardcode.
- The provider is built behind `@lru_cache` so it's created once per process, after fork.
