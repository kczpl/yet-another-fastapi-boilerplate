---
paths:
  - "app/integrations/**/*.py"
  - "app/features/**/services/**/*.py"
  - "app/workers/**/*.py"
---

# Integrations

Keep vendor interactions behind small functions/clients in `integrations/<vendor>/` or in a
feature's agent wrapper. Prefer async I/O; run sync SDK operations in a thread when called from
async code. Build network clients lazily after fork. Do not add an unused generic client base.

Sentry initializes only with a DSN in staging/production. FastAPI/Starlette capture server
exceptions; SQLAlchemy adds spans. Celery/Pydantic AI integrations are added only when installed.
Worker cron monitors are enabled; prompt capture and local variables remain disabled.

The event scrubber is keyword-based and best-effort, not permission to log sensitive data.
Don't log secrets, raw bodies or prompts. SDK initialization imports must not make optional
packages mandatory for core API startup.

Bedrock uses the standard AWS credential chain including session tokens and profiles. Don't
invent custom AWS credential names in application settings. See ai-agents.md for lifecycle.
