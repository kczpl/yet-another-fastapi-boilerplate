---
paths:
  - "tests/**/*.py"
---

# Testing

Use pytest + pytest-asyncio in auto mode. Tests and async fixtures use the same session loop,
so pooled DB connections don't cross loops. `just test` waits for PostgreSQL 18 readiness.

Schemas come from Alembic migrations, not create_all. Each DB test opens an outer transaction;
its AsyncSession uses `join_transaction_mode="create_savepoint"`. Service commits release the
savepoint; teardown rolls back the outer transaction. Never mock the DB or commit method.
If code under test rolls back, commit factory setup first so its rows survive that savepoint.
Rollback expires ORM attributes; save ids before the rollback when needed.

Mirror features under `tests/features/<domain>/`: route tests, repository tests and services/.
Core pure tests should run without requesting DB fixtures. Factories in `tests/factories/`
build minimal valid rows; the fixture binds imported factory subclasses to the test session.
Pass relationships/FKs explicitly; no speculative factory derivation framework.

Patch third-party APIs and Celery publishing. `mock_celery` prevents task `.delay()` /
`.apply_async()` from contacting Redis. AI tests use importorskip when extras are absent and
patch the async model wrapper. Never call live models in CI. Workers and AI must remain
optional: CI runs core, workers and AI separately, including runtime image imports.

Test observable behavior and important boundaries: transaction ownership, constraints,
serialization, out-of-range pagination, middleware 500 responses, request limits and migrations.
Avoid tests that just repeat implementation details. Pyright checks all modules with all extras.
