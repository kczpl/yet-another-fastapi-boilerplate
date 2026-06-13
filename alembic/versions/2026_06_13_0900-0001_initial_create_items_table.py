"""create items table

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-13

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "items",
        # uuidv7() is a native Postgres 18 function; ORM inserts supply the id via
        # app.utils.uuid.uuid7, raw SQL inserts fall back to this server default.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        # SHORT name — the naming convention in app/core/db/base.py expands it to
        # "items_status_check".
        sa.CheckConstraint("status IN ('active', 'archived')", name="status"),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("items", schema="public")
