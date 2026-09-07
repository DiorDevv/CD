"""SOC/DLP bo'lim paneli — topshiriqlar va yig'ma statistika sxemalari."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.section_todo import TodoScope
from app.schemas.dynamic import ColumnValueCount

TEXT_MAX = 500


# --- Topshiriqlar ---------------------------------------------------------------


class TodoCreate(BaseModel):
    scope: TodoScope
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    due_date: date | None = None


class TodoUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=TEXT_MAX)
    is_done: bool | None = None
    due_date: date | None = None  # PATCH'da `null` berilsa — muddat olib tashlanadi


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section: str
    scope: TodoScope
    owner_id: uuid.UUID
    owner_name: str | None = None
    text: str
    is_done: bool
    due_date: date | None
    position: int
    created_at: datetime
    done_at: datetime | None


# --- Yig'ma statistika --------------------------------------------------------


class SectionTotals(BaseModel):
    tables: int = 0
    rows: int = 0
    done: int = 0
    open: int = 0
    added_7d: int = 0


class SectionTableStat(BaseModel):
    id: uuid.UUID
    name: str
    row_count: int
    done_count: int
    updated_at: datetime
    # birinchi select/multi_select ustun bo'yicha taqsimot (bo'lsa)
    breakdown_label: str | None = None
    breakdown: list[ColumnValueCount] = Field(default_factory=list)


class RecentChange(BaseModel):
    table_id: uuid.UUID
    table_name: str
    row_id: uuid.UUID
    action: str
    changed_by: uuid.UUID | None
    changed_by_name: str | None
    changed_at: datetime


class TrendPoint(BaseModel):
    day: date
    count: int


class SectionSummaryOut(BaseModel):
    section: str
    totals: SectionTotals
    tables: list[SectionTableStat] = Field(default_factory=list)
    recent: list[RecentChange] = Field(default_factory=list)
    trend: list[TrendPoint] = Field(default_factory=list)
