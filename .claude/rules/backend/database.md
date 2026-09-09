---
paths:
  - "app/**/*.py"
  - "alembic/**/*.py"
---

# Database

PostgreSQL 18, SQLAlchemy 2 async API, psycopg3. Shared Base/engine/session factories live in
`app/core/db.py`. Each feature owns `models.py` and `repository.py`. Register models explicitly
in `app/models.py` for Alembic; avoid automatic import discovery.

## Models

- UUIDv7 primary keys: `default=uuid.uuid7` from Python 3.14 and `server_default=text("uuidv7()")`.
- Timezone-aware timestamps; Python `utc_now` defaults plus matching `server_default=text("now()")`.
  ORM `onupdate=utc_now` applies to ORM updates; raw SQL callers set updated_at explicitly.
- String + CheckConstraint for statuses; no PostgreSQL ENUM dependency.
- Explicit public schema. Naming conventions produce `{table}_pkey`, `{table}_{column}_key`,
  `{table}_{column}_fkey`, `{table}_{constraint}_check`, `{table}_{column}_idx`.
- Match server defaults, constraints and indexes between models and migrations so `alembic check`
  stays clean. Declare indexes used by real queries in metadata too; don't hide them from autogenerate.
- Add indexes for actual query patterns; avoid speculative indexing.
- Foreign keys specify appropriate ondelete behavior. Bind SQL parameters; never interpolate input.

## Transactions and queries

Repositories query/mutate/flush and never commit. Route-facing services commit their use case;
worker services use the runner's `session_scope()`. Never add a commit flag to repositories.
Load relationships explicitly to avoid N+1 and MissingGreenlet errors. Never share AsyncSession
across concurrent tasks; each concurrent unit of work needs its own session.

Paged queries use stable ordering and a separate count so empty pages retain totals. Two queries
at READ COMMITTED may observe concurrent writes; choose stronger snapshot semantics only when
product requirements demand them.

## Migrations

`just makemigration "description"` generates revisions; post-write Ruff hooks format them.
Migrations are static and include upgrade/downgrade. All table operations name schema="public".
The Alembic URL comes from the same env/.env settings as the API, with ConfigParser escaping.

Tests create schemas by applying migrations. CI runs upgrade → check → downgrade → upgrade.
Compose runs one migration service before API/workers; images do not migrate on every startup.
Never run production migrations yourself. For rolling deployments, use expand/migrate/contract
changes so old and new replicas can coexist.
