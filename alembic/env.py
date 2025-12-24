from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_schema_type() -> str:
    config_file = config.config_file_name or ""
    if "public" in config_file:
        return "public"
    elif "tenants" in config_file:
        return "tenant"
    raise ValueError("Use: alembic -c alembic/alembic_public.ini OR alembic -c alembic/alembic_tenants.ini")


def run_migrations_for_schema(
    connection: Connection,
    schema_name: str,
) -> None:
    """Run migrations for a specific schema."""
    connection.execute(text(f"SET search_path TO {schema_name}"))

    if schema_name != "public":
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=schema_name,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    schema_type = get_schema_type()

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        if schema_type == "public":
            await connection.run_sync(
                run_migrations_for_schema,
                schema_name="public",
            )
        elif schema_type == "tenant":
            result = await connection.execute(text("SELECT id FROM public.tenants ORDER BY id"))
            tenant_ids = [row[0] for row in result.fetchall()]

            if not tenant_ids:
                print("No tenants found in public.tenants table")
                return

            total = len(tenant_ids)
            for idx, tenant_id in enumerate(tenant_ids, 1):
                schema_name = f"tenant_{tenant_id}"
                print(f"[{idx}/{total}] Migrating schema: {schema_name}")
                await connection.run_sync(
                    run_migrations_for_schema,
                    schema_name=schema_name,
                )
        await connection.commit()

    await connectable.dispose()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
