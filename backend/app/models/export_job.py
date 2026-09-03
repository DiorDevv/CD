"""Jadval eksporti — fon (background) job.

Sinxron `GET /tables/{id}/export` so'rovchi brauzerni eksport tugaguncha band
qiladi — kichik jadval uchun yaxshi, katta jadval uchun yaroqsiz. Bu jadval
ishni server tomonida bajarishga imkon beradi: job yaratiladi (`pending`), fon
vazifasi uni ishlatadi (`running` -> `done`/`failed`), natija `EXPORT_DIR` ga
fayl sifatida yoziladi, mijoz ulanishni ushlab turmasdan holatni so'rab turadi.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExportJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class ExportFormat(str, enum.Enum):
    csv = "csv"
    json = "json"
    xlsx = "xlsx"


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dynamic_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section: Mapped[str] = mapped_column(String(16), nullable=False)  # RBAC uchun (job yaratilgandagi bo'lim)

    status: Mapped[ExportJobStatus] = mapped_column(
        SAEnum(ExportJobStatus, name="export_job_status"),
        default=ExportJobStatus.pending,
        nullable=False,
        index=True,
    )
    format: Mapped[ExportFormat] = mapped_column(
        SAEnum(ExportFormat, name="export_format"), nullable=False
    )
    # Job yaratilgandagi filtrlar (q, sort) — UI'da nima eksport qilinganини ko'rsatish uchun.
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Tayyor faylning SHA-256 summasi — qabul qiluvchi (to'g'ridan yoki havola
    # orqali) keyinchalik faylning aynan shu server chiqargan nusxa ekanini
    # tekshira olishi uchun.
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vaqtli, admin bergan havola — tayyor eksportni tizimga kirmasdan yuklab
    # olish uchun. DB'da faqat token hash saqlanadi (refresh token bilan bir xil
    # shakl). None/None — faol havola yo'q; yangi havola eskisini almashtiradi.
    share_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    share_created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
