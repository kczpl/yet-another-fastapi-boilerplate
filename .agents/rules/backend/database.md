---
paths:
  - "app/features/*/services/**/*.py"
  - "app/features/*/models.py"
  - "app/features/*/repository.py"
  - "app/models.py"
  - "app/core/db.py"
  - "alembic/**"
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
  Composite indexes/constraints include all participating column names, joined with underscores.
- Match server defaults, constraints and indexes between models and migrations so `alembic check`
  stays clean. Declare indexes used by real queries in metadata too; don't hide them from autogenerate.
- Add indexes for actual query patterns; avoid speculative indexing. Index each foreign key
  column: PostgreSQL does not do it. Use a partial index for a column with few values
  (`postgresql_where=text("status = 'active'")`), not a plain index on that column.
- Foreign keys specify appropriate ondelete behavior. Bind SQL parameters; never interpolate input.

## Transactions and queries

Repositories query/mutate/flush and never commit. Route-facing services commit their use case;
worker services use the runner's `session_scope()`. Never add a commit flag to repositories.
Load relationships explicitly to avoid N+1 and MissingGreenlet errors. Never share AsyncSession
across concurrent tasks; each concurrent unit of work needs its own session.

An open transaction holds a pool connection. Commit before a slow call (LLM, HTTP, S3), then
write in a new short transaction. A slow provider otherwise empties the pool of the process.
`IDLE_IN_TRANSACTION_TIMEOUT` (default 60 s) makes PostgreSQL end such a session, also in
development. Behind PgBouncer, set it to 0 and configure the timeout on the database role.

Paged queries use stable ordering and a separate count so empty pages retain totals. Two queries
at READ COMMITTED may observe concurrent writes; choose stronger snapshot semantics only when
product requirements demand them.

Concurrent writers:

- For read-modify-write on a shared row (a counter, a balance, a status change), lock the row
  with `with_for_update()` (`get_item_for_update`) or write with `on_conflict_do_update()`.
- Do not check and then insert. Insert and catch `IntegrityError` of the unique constraint.
- Lock rows in the same order in each use case, so two transactions cannot deadlock.

For user search, use `column.icontains(value, autoescape=True)` or `istartswith(...)`. Never
build `ilike(f"%{value}%")`: `%` and `_` in the input then act as wildcards.

## Migrations

`just makemigration "description"` generates revisions; post-write Ruff hooks format them.
Filenames use `YYYY_MM_DD_HHMM-<revision>_<slug>.py` in UTC. Hooks use the active Python
environment, which must include Ruff; deployment images only apply existing migrations.
Migrations are static and include upgrade/downgrade. All table operations name schema="public".
The Alembic URL comes from the same env/.env settings as the API, with ConfigParser escaping.
The version table is explicitly in public. Autogenerate only inspects registered model tables
in public and ignores unrelated tables. Removing a model therefore requires an explicit
drop_table migration; review all generated operations, including destructive column changes.

Tests create schemas by applying migrations. CI runs upgrade → check → downgrade → upgrade.
Compose runs one migration service before API/workers; images do not migrate on every startup.
Never run production migrations yourself. `tests/migrations/test_heads.py` keeps one head; after
a rebase, set `down_revision` to the new head (`git.md`).

A rolling deployment runs old and new code on the new schema at the same time. Add freely;
remove, narrow or rename only after the old code stops using it (expand, migrate, contract).

| Operation | Safe in one deployment |
|---|---|
| Add a nullable column, or a column with `server_default` | Yes |
| Create a table; create an index (`CONCURRENTLY` on a large table) | Yes |
| Widen a type (`String(50)` to `String(255)`) | Yes |
| Drop a column or a table | Only when no running code uses it |
| Rename a column or a table | No: add, backfill, switch the code, then drop |
| Set `NOT NULL` on an existing column | No: add a default, backfill, then alter |
| Narrow or change a type | No: add a new column, copy the data, then drop the old one |

`CREATE INDEX CONCURRENTLY` cannot run in a transaction. Call
`op.create_index(..., postgresql_concurrently=True)` in `with op.get_context().autocommit_block():`.
