"""Bo'lim (SOC/DLP) topshiriqlari — yengil "nima qilmoqchiman" ro'yxati.

Dinamik jadvallardan alohida: sobit maydonlar, tez qo'shish uchun.
`scope`:
  * personal — faqat `owner_id` ko'radi/boshqaradi
  * shared   — bo'limdagi hamma ko'radi; yozish huquqi borlar boshqaradi
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TodoScope(str, enum.Enum):
    personal = "personal"
    shared = "shared"


class SectionTodo(Base):
    __tablename__ = "section_todos"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # soc | dlp
    scope: Mapped[TodoScope] = mapped_column(
        SAEnum(TodoScope, name="todo_scope"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
