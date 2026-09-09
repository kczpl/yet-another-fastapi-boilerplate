---
paths:
  - "app/core/agents.py"
  - "app/**/agents/**"
---

# Optional Pydantic AI / Bedrock

Install the `ai` extra. Each feature's `agents/` owns its output model, static prompt,
cached Agent factory, and async wrapper. Shared provider/model/settings/usage helpers live
in `app/core/agents.py`.

- Create Agent/provider/model on first use via cached factories, never at module import.
  Caching is safe for prefork only when the parent hasn't constructed the client.
- Standard AWS credential chain; configure BEDROCK_REGION and a model enabled for the account.
- Keep system instructions static; pass dynamic input as the user prompt or explicit deps.
- Set output_type, name, retries and usage_limits. Log token usage and best-effort cost after runs.
- Return typed outputs. Validators normalize useful data and reject invalid domain results.
  Don't silently relax invariants on the final retry unless the product has a review workflow.
- ModelRetry must reach the agent loop. Handle only specific failures at the relevant boundary.
- Put tools/validators in separate modules only when the agent grows enough to benefit, and
  explicitly register them in its factory; no mandatory side-effect barrel package.
- LLM-bound background work uses the heavy queue. No live LLM calls in normal tests or CI.

Tests validate output models and patch the async wrapper in service tests. Importing the agent
module must not fetch AWS credentials or open a network connection.
