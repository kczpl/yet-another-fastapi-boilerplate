import io
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Column, Index, Integer, MetaData, Table, create_engine, text

from app.core.config import database_config
from app.core.db import NAMING_CONVENTION, to_psycopg_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migration_config(tmp_path: Path) -> Config:
    migration_root = tmp_path / "alembic"
    shutil.copytree(PROJECT_ROOT / "alembic", migration_root, ignore=shutil.ignore_patterns("__pycache__"))
    config = Config(str(PROJECT_ROOT / "alembic/alembic.ini"))
    config.set_main_option("script_location", str(migration_root))
    config.set_main_option("version_locations", str(migration_root / "versions"))
    return config


def test_generated_revision_has_utc_name_and_passes_lint(migration_config: Config):
    revision = command.revision(migration_config, message="add example records")
    assert revision is not None
    assert not isinstance(revision, list)
    path = Path(revision.path)
    content = path.read_text()
    match = re.search(r"Create Date: (.+)", content)
    assert match is not None
    created_at = datetime.fromisoformat(match[1])
    offset = created_at.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0
    assert path.name == f"{created_at:%Y_%m_%d_%H%M}-{revision.revision}_add_example_records.py"
    subprocess.run(  # noqa: S603 — fixed local tool, generated temporary migration
        [sys.executable, "-m", "ruff", "check", "--config", str(PROJECT_ROOT / "pyproject.toml"), str(path)],
        check=True,
    )


def test_offline_sql_qualifies_version_and_application_tables(migration_config: Config):
    output = io.StringIO()
    migration_config.output_buffer = output
    command.upgrade(migration_config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE public.alembic_version" in sql
    assert "CREATE TABLE public.items" in sql
    assert "CONSTRAINT items_pkey" in sql
    assert "CONSTRAINT items_status_check" in sql


def test_autogenerate_ignores_unmanaged_tables_with_custom_search_path(migrated_db, monkeypatch):
    engine = create_engine(to_psycopg_url(database_config.DATABASE_URL))
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA migration_test_external"))
            connection.execute(text("CREATE TABLE migration_test_external.items (id integer)"))
            connection.execute(text("CREATE TABLE public.migration_test_unmanaged (id integer)"))
        url = engine.url.update_query_dict({"options": "-csearch_path=migration_test_external,public"})
        monkeypatch.setattr(database_config, "DATABASE_URL", url.render_as_string(hide_password=False))
        config = Config(str(PROJECT_ROOT / "alembic/alembic.ini"))
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT to_regclass('migration_test_external.alembic_version')")) is None
            assert (
                connection.scalar(text("SELECT version_num FROM public.alembic_version"))
                == ScriptDirectory.from_config(config).get_current_head()
            )
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS public.migration_test_unmanaged"))
            connection.execute(text("DROP TABLE IF EXISTS migration_test_external.items"))
            connection.execute(text("DROP SCHEMA IF EXISTS migration_test_external"))
        engine.dispose()


def test_composite_index_names_include_all_columns():
    table = Table(
        "example",
        MetaData(naming_convention=NAMING_CONVENTION),
        Column("owner_id", Integer),
        Column("first", Integer),
        Column("second", Integer),
    )
    first = Index(None, table.c.owner_id, table.c.first)
    second = Index(None, table.c.owner_id, table.c.second)
    assert first.name == "example_owner_id_first_idx"
    assert second.name == "example_owner_id_second_idx"
