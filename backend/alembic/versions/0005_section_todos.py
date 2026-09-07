"""section_todos — SOC/DLP bo'lim topshiriqlari (personal + shared)

Revision ID: 0005_section_todos
Revises: 0004_export_jobs
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_section_todos"
down_revision: Union[str, None] = "0004_export_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_scope = postgresql.ENUM("personal", "shared", name="todo_scope", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("personal", "shared", name="todo_scope").create(bind, checkfirst=True)

    op.create_table(
        "section_todos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section", sa.String(16), nullable=False),
        sa.Column("scope", _scope, nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_section_todos_section", "section_todos", ["section"])
    op.create_index("ix_section_todos_owner_id", "section_todos", ["owner_id"])
    op.create_index(
        "ix_section_todos_lookup", "section_todos", ["section", "scope", "owner_id"]
    )


def downgrade() -> None:
    op.drop_table("section_todos")
    postgresql.ENUM(name="todo_scope").drop(op.get_bind(), checkfirst=True)
