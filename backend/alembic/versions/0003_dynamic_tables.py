"""dynamic tables: dynamic_tables, dynamic_columns, dynamic_rows, dynamic_row_revisions

Revision ID: 0003_dynamic_tables
Revises: 0002_hardening
Create Date: 2026-09-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_dynamic_tables"
down_revision: Union[str, None] = "0002_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

table_section = postgresql.ENUM("soc", "dlp", "shared", name="table_section")
column_type = postgresql.ENUM(
    "text",
    "long_text",
    "number",
    "boolean",
    "date",
    "datetime",
    "select",
    "multi_select",
    "user",
    name="column_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    table_section.create(bind, checkfirst=True)
    column_type.create(bind, checkfirst=True)

    op.create_table(
        "dynamic_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section", postgresql.ENUM(name="table_section", create_type=False), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("section", "slug", name="uq_dyn_table_section_slug"),
    )
    op.create_index("ix_dynamic_tables_section", "dynamic_tables", ["section"])

    op.create_table(
        "dynamic_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("type", postgresql.ENUM(name="column_type", create_type=False), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("table_id", "key", name="uq_dyn_column_table_key"),
    )
    op.create_index("ix_dynamic_columns_table_id", "dynamic_columns", ["table_id"])

    op.create_table(
        "dynamic_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dynamic_rows_table_id", "dynamic_rows", ["table_id"])
    op.create_index(
        "ix_dynamic_rows_data_gin", "dynamic_rows", ["data"], postgresql_using="gin"
    )

    op.create_table(
        "dynamic_row_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dynamic_row_revisions_table_id", "dynamic_row_revisions", ["table_id"])
    op.create_index("ix_dynamic_row_revisions_row_id", "dynamic_row_revisions", ["row_id"])
    op.create_index("ix_dynamic_row_revisions_changed_at", "dynamic_row_revisions", ["changed_at"])


def downgrade() -> None:
    op.drop_table("dynamic_row_revisions")
    op.drop_table("dynamic_rows")
    op.drop_table("dynamic_columns")
    op.drop_index("ix_dynamic_tables_section", table_name="dynamic_tables")
    op.drop_table("dynamic_tables")
    column_type.drop(op.get_bind(), checkfirst=True)
    table_section.drop(op.get_bind(), checkfirst=True)
