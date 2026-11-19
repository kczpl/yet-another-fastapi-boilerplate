import uuid

import pytest
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

import app.models  # noqa: F401  # registers every model on Base.metadata
from app.core.db import Base


def _leading_columns(table: Table) -> list[Column]:
    keys = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, PrimaryKeyConstraint | UniqueConstraint)
    ]
    return [next(iter(group.columns)) for group in [*table.indexes, *keys] if len(group.columns)]


def _is_uuid7_key(column: Column) -> bool:
    default = getattr(column.default, "arg", None)
    server_default = getattr(column.server_default, "arg", None)
    return getattr(default, "__wrapped__", default) is uuid.uuid7 and str(server_default) == "uuidv7()"


def _column_problems(table: Table, column: Column) -> list[str]:
    problems = []
    if isinstance(column.type, DateTime) and not column.type.timezone:
        problems.append(f"{column.name}: DateTime without timezone")
    if isinstance(column.type, Enum):
        problems.append(f"{column.name}: Enum; use String and a CheckConstraint")
    # PostgreSQL does not index a foreign key column by itself.
    if column.foreign_keys and not any(leading is column for leading in _leading_columns(table)):
        problems.append(f"{column.name}: foreign key without an index")
    return problems


def _table_problems(table: Table) -> list[str]:
    problems = [] if table.schema == "public" else ["schema is not public"]
    key = list(table.primary_key.columns)
    if len(key) == 1 and not key[0].foreign_keys and not _is_uuid7_key(key[0]):
        problems.append(f"{key[0].name}: primary key without uuid7 and uuidv7() defaults")
    for column in table.columns:
        problems.extend(_column_problems(table, column))
    return problems


def test_finds_each_convention_problem():
    metadata = MetaData()
    Table("parents", metadata, Column("id", Integer, primary_key=True), schema="public")
    bad = Table(
        "children",
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")),
        Column("parent_id", Integer, ForeignKey("public.parents.id")),
        Column("created_at", DateTime()),
        Column("kind", Enum("a", "b", name="kind")),
    )

    assert _table_problems(bad) == [
        "schema is not public",
        "id: primary key without uuid7 and uuidv7() defaults",
        "parent_id: foreign key without an index",
        "created_at: DateTime without timezone",
        "kind: Enum; use String and a CheckConstraint",
    ]


@pytest.mark.parametrize("table", Base.metadata.sorted_tables, ids=lambda table: table.name)
def test_model_follows_the_database_conventions(table: Table):
    assert _table_problems(table) == [], "Follow the model conventions of .agents/rules/backend/database.md."
