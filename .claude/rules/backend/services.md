---
paths:
  - "app/features/**/services/**/*.py"
  - "app/services/**/*.py"
---

# Services

One class per meaningful use case under `features/<domain>/services/`, with a `call()` method.
The shared `Service` stores an `AsyncSession`. A simple function is also fine when no state or
related behavior needs grouping. Do not extract every line into its own method.

- Services call their feature's repository and enforce business invariants.
- HTTP identity/access belongs in route dependencies. Invariants that must also hold in a
  background task or another caller belong in the service, not only in HTTP checks.
- Accept already-loaded domain objects when available; avoid redundant fetches and async lazy loads.
- Return domain entities or typed results, without API envelopes or Pydantic response serialization.
- Route-facing write services commit at the end of their use case. Repositories only flush.
- Worker services leave commit/rollback to `session_scope()` through `run_service()`.
- Compose related writes under one transaction owner; don't nest committing services.
- Queue only after the relevant data is committed. If commit and publish must be atomic,
  introduce an outbox for that workflow; a direct `.delay()` cannot provide that guarantee.

`CreateItemService`, `ListItemsService` and `SummarizeItemService` demonstrate these boundaries.
