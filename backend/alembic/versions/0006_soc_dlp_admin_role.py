"""user_role enum'iga soc_dlp_admin (SOC + DLP) rolini qo'shish

Revision ID: 0006_soc_dlp_admin_role
Revises: 0005_section_todos
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_soc_dlp_admin_role"
down_revision: Union[str, None] = "0005_section_todos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PG12+ da ADD VALUE tranzaksiya ichida ishlaydi (qiymat shu tranzaksiyada ishlatilmaydi)
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'soc_dlp_admin'")


def downgrade() -> None:
    # Postgres enum qiymatini o'chirib bo'lmaydi — shu roldagi foydalanuvchilarni
    # xavfsiz tomonga (soc_admin) qaytaramiz, qiymatning o'zi tipda qoladi.
    op.execute("UPDATE users SET role = 'soc_admin' WHERE role = 'soc_dlp_admin'")
