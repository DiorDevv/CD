"""Dinamik jadvallar — foydalanuvchi o'zi tuzadigan jadval/ustun/qatorlar.

Ustunlar runtime'da haqiqiy DDL bilan emas, metama'lumot sifatida saqlanadi;
qator qiymatlari `dynamic_rows.data` (JSONB) da yashaydi. Tekshiruv API qatlamida
ustun ta'rifiga qarab bajariladi (`app/services/dynamic_values.py`).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TableSection(str, enum.Enum):
    soc = "soc"
    dlp = "dlp"
    shared = "shared"


class ColumnType(str, enum.Enum):
    text = "text"
    long_text = "long_text"
    number = "number"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    select = "select"
    multi_select = "multi_select"
    user = "user"


class DynamicTable(Base):
    __tablename__ = "dynamic_tables"
    __table_args__ = (UniqueConstraint("section", "slug", name="uq_dyn_table_section_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section: Mapped[TableSection] = mapped_column(
        SAEnum(TableSection, name="table_section"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    columns: Mapped[list["DynamicColumn"]] = relationship(
        "DynamicColumn",
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="DynamicColumn.position",
    )


class DynamicColumn(Base):
    __tablename__ = "dynamic_columns"
    __table_args__ = (UniqueConstraint("table_id", "key", name="uq_dyn_column_table_key"),)

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("dynamic_tables.id", ondelete="CASCADE"), index=True, nullable=False
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)          # barqaror mashina kaliti
    label: Mapped[str] = mapped_column(String(120), nullable=False)       # ko'rinadigan nom (o'zgaruvchan)
    type: Mapped[ColumnType] = mapped_column(
        SAEnum(ColumnType, name="column_type"), nullable=False
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    table: Mapped["DynamicTable"] = relationship("DynamicTable", back_populates="columns")


class DynamicRow(Base):
    __tablename__ = "dynamic_rows"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("dynamic_tables.id", ondelete="CASCADE"), index=True, nullable=False
    )
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DynamicRowRevision(Base):
    __tablename__ = "dynamic_row_revisions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("dynamic_tables.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # row_id FK EMAS — qator o'chirilganda ham tarix qoladi
    row_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # create | update | delete
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # o'zgarishdan keyingi holat
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
