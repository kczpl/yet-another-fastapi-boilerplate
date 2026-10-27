# Testing

Use pytest + pytest-asyncio in auto mode. Tests and async fixtures use the same session loop,
so pooled DB connections don't cross loops. `just test` waits for PostgreSQL 18 readiness.
`[tool.pytest]` enables `strict` and turns warnings into errors. To ignore a third-party
warning, add an exact `filterwarnings` entry with the reason.

Schemas come from Alembic migrations, not create_all. Each DB test opens an outer transaction;
its AsyncSession uses `join_transaction_mode="create_savepoint"`. Service commits release the
savepoint; teardown rolls back the outer transaction. Never mock the DB or commit method.
If code under test rolls back, commit factory setup first so its rows survive that savepoint.
Rollback expires ORM attributes; save ids before the rollback when needed.
To test `session_scope()`, monkeypatch `app.core.db.SessionLocal` with a savepoint session
factory on `db_session.bind`. The worker runner test calls the real signal handlers and only reads.

Mirror features under `tests/features/<domain>/`: route tests, repository tests and services/.
Core pure tests should run without requesting DB fixtures. Factories in `tests/factories/`
subclass `BaseFactory[Model]` and build minimal valid rows. `await Factory.create()` returns the
typed model. The fixture binds imported factory subclasses to the test session.
Pass relationships/FKs explicitly; no speculative factory derivation framework.

Patch third-party APIs and Celery publishing. `mock_celery` prevents task `.delay()` /
`.apply_async()` from contacting Redis. AI tests use importorskip when extras are absent and
patch the async model wrapper. `tests/conftest.py` sets `ALLOW_MODEL_REQUESTS = False`, so a
real model request fails. Never call live models in CI. Workers and AI must remain
optional: CI runs core, workers and AI separately, including runtime image imports.
Routing tests use a real Kombu memory transport and an explicit producer; they require no Redis.

Test observable behavior and important boundaries: transaction ownership, constraints,
serialization, out-of-range pagination, middleware 500 responses, request limits and migrations.
Avoid tests that just repeat implementation details. Pyright checks all modules with all extras.

`tests/conftest.py` sets `RATE_LIMIT_PER_MINUTE=0`, so a long suite never reaches the limit.
Test the limit on a `SecurityMiddleware` with a fake clock, or on a throwaway app after a
monkeypatch of `api_config`.
