---
paths:
  - "app/**/*.py"
  - "alembic/**/*.py"
---

## Database Conventions

Naming conventions defined in `app/core/db/base.py` (applied automatically by SQLAlchemy MetaData, and by Alembic ops because `env.py` configures `target_metadata`):

| Object | Pattern | Example |
|--------|---------|---------|
| Primary key | `{table}_pkey` | `items_pkey` |
| Foreign key | `{table}_{column}_fkey` | `orders_item_id_fkey` |
| Index | `{table}_{column}_idx` | `items_status_idx` |
| Unique | `{table}_{column}_key` | `items_slug_key` |
| Check | `{table}_{name}_check` | `items_status_check` |

General: `lowercase_snake_case`, plural table names, FK columns as `{referenced_table_singular}_id`.

### Primary Keys — UUIDv7

```python
# Migration (Postgres 18 has a native uuidv7() function)
sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()"))
# Model
from app.utils.uuid import uuid7
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
```

`uuid7` (in `app/utils/uuid.py`) wraps `uuid_utils.compat.uuid7` and returns a stdlib `uuid.UUID`. Always use it instead of `uuid.uuid4` so ORM-created records get timestamp-ordered IDs that match the DB-side server default.

### No Enums

Never use PostgreSQL ENUM types — use `String(n)` + `CheckConstraint`.

### Indexing

- `index=True` on `mapped_column` is allowed for single-column indexes (FK, unique fields)
- Non-unique composite/complex indexes live ONLY in migrations — never as `Index()` in model `__table_args__`
- UNIQUE indexes (incl. partial) are declared in BOTH the migration and the model `__table_args__` — the test schema is built from `Base.metadata.create_all`, so uniqueness the code relies on (`IntegrityError` handling) must exist in models too
- Avoid overindexing — only create indexes that serve actual queries
- Never index low-cardinality columns directly (e.g. `status` with 3 values) — use partial indexes instead
- Composite indexes for common query patterns: `["user_id", "status"]`
- Partial indexes for soft-delete tables: `postgresql_where=sa.text("deleted_at IS NULL")`

### Timestamps

Always `DateTime(timezone=True)` — never without timezone:

```python
# Migration
sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))
# Model — use utc_now from app.utils.time
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
```

### Column Types

| Purpose | Type |
|---------|------|
| Bounded text | `String(n)` |
| Unbounded text | `Text` |
| Money (cents) | `BigInteger` |
| Structured data | `JSONB` |

### Foreign Keys & Schema

- Always specify `ondelete`: `CASCADE` for ownership, `SET NULL` for optional references
- All migrations: `schema="public"` on every operation
- All models: `__table_args__ = {"schema": "public"}`

### Transaction Ownership

Repository functions (`app/repositories/*/crud.py`) never call `commit()` — use `await db.flush()` to materialize IDs and defaults. The transaction belongs to the caller:

- Route-facing services commit explicitly (`await self.db.commit()`).
- Celery tasks get auto-commit from `async_db_session` (via `run_service`).

Never add a `commit: bool` parameter to a repository function — if a caller needs different batching, it controls the transaction itself.

## SQL-First Approach

- Prefer SQL for complex operations - databases are faster at joins and aggregations
- Always use the ORM / bound parameters (never string-format user input) to prevent SQL injection
- Use SQL to build nested JSON responses rather than Python loops
- Avoid `SELECT *`, get only the columns you need
- Avoid `DISTINCT` to "fix" duplicate rows from a join - it hides the real problem
- Always check against the N+1 problem when you write a query
- Always use connection pooling - never create connections on-demand

For complex raw SQL, bind every parameter:

```python
query = text("""
    SELECT u.id, COUNT(o.id) AS order_count
    FROM users u
    LEFT JOIN orders o ON o.user_id = u.id
    WHERE u.created_at > :start_date AND u.status = :status
    GROUP BY u.id
    HAVING COUNT(o.id) > :min_orders
""")
result = await db.execute(query, {"start_date": ..., "status": ..., "min_orders": ...})
```

## Alembic & Migrations Patterns

Config is `alembic/alembic.ini`. `DATABASE_URL` (env) overrides `sqlalchemy.url`.

- Keep migrations static and revertable - no dynamic schema generation
- Generate with `uv run alembic -c alembic/alembic.ini revision --autogenerate -m "create items table"` (or `just makemigration "..."`)
- Always provide both `upgrade()` and `downgrade()`
- Descriptive slug — the file template is `YYYY_MM_DD_HHMM-<rev>_<slug>.py`

```python
# upgrade: SHORT name — the base.py convention expands it to "items_status_check"
op.create_check_constraint("status", "items", "status IN ('active', 'archived')", schema="public")
# for nullable columns add OR column IS NULL
op.create_check_constraint("kind", "items", "kind IN ('a', 'b') OR kind IS NULL", schema="public")
op.create_index("items_status_idx", "items", ["status"], schema="public")

# downgrade: use the FULL generated name
op.drop_constraint("items_status_check", "items", schema="public")
```

### Zero-Downtime Migrations (production)

If production rolls API replicas one at a time, **old and new code run against the new schema at the same time** during a deploy. Migrations must be backward-compatible — the still-running old replica must survive them.

**Thumb rule: add freely, remove/narrow/rename only after old code stops using it.** Split breaking changes across releases: expand now → backfill + switch code → contract in a later deploy.

| Operation | Safe in one deploy? |
|-----------|---------------------|
| `add_column` (nullable, or with `server_default`) | ✅ |
| `create_table`, `create_index` (`CONCURRENTLY` on big tables) | ✅ |
| Widen type (`String(50)` → `String(255)`) | ✅ |
| `drop_column`, `drop_table` | ❌ contract step — only when no running code uses it |
| Rename column/table | ❌ split into add → backfill → drop |
| `NOT NULL` on existing column | ❌ add nullable + `server_default` → backfill → `alter` to NOT NULL |
| Narrow/change type | ❌ new column → migrate data → drop old |

> Important: never run migrations against production by yourself.
