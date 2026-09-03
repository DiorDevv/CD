"""export_jobs — jadval eksporti (fon job + ulashish havolasi)

Revision ID: 0004_export_jobs
Revises: 0003_dynamic_tables
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_export_jobs"
down_revision: Union[str, None] = "0003_dynamic_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `create_type=False` -> ustun ta'rifi CREATE TYPE emitlamaydi; turlarni
# quyida bir marta o'zimiz (checkfirst bilan) yaratamiz.
_status = postgresql.ENUM(
    "pending", "running", "done", "failed", "cancelled",
    name="export_job_status", create_type=False,
)
_format = postgresql.ENUM("csv", "json", "xlsx", name="export_format", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "pending", "running", "done", "failed", "cancelled", name="export_job_status"
    ).create(bind, checkfirst=True)
    postgresql.ENUM("csv", "json", "xlsx", name="export_format").create(bind, checkfirst=True)

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", sa.String(16), nullable=False),
        sa.Column("status", _status, nullable=False, server_default="pending"),
        sa.Column("format", _format, nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("share_token_hash", sa.String(64), nullable=True),
        sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "share_created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_export_jobs_table_id", "export_jobs", ["table_id"])
    op.create_index("ix_export_jobs_status", "export_jobs", ["status"])
    op.create_index("ix_export_jobs_created_at", "export_jobs", ["created_at"])
    op.create_index("ix_export_jobs_share_token_hash", "export_jobs", ["share_token_hash"])


def downgrade() -> None:
    op.drop_table("export_jobs")
    postgresql.ENUM(name="export_job_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="export_format").drop(op.get_bind(), checkfirst=True)
