import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.dynamic import ColumnType, TableSection
from app.models.user import UserRole

NAME_MAX = 120
DESC_MAX = 500
LABEL_MAX = 120


# --- Ustunlar ---------------------------------------------------------------


class ColumnCreate(BaseModel):
    label: str = Field(min_length=1, max_length=LABEL_MAX)
    type: ColumnType
    config: dict[str, Any] = Field(default_factory=dict)
    position: int | None = Field(default=None, ge=0)


class ColumnUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=LABEL_MAX)
    type: ColumnType | None = None
    config: dict[str, Any] | None = None
    position: int | None = Field(default=None, ge=0)


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    label: str
    type: ColumnType
    config: dict[str, Any]
    position: int


# --- Jadvallar ------------------------------------------------------------------


class TableCreate(BaseModel):
    section: TableSection
    name: str = Field(min_length=1, max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=DESC_MAX)
    columns: list[ColumnCreate] = Field(default_factory=list, max_length=100)


class TableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=DESC_MAX)
    position: int | None = Field(default=None, ge=0)
    is_archived: bool | None = None


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section: TableSection
    name: str
    slug: str
    description: str | None
    position: int
    is_archived: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    column_count: int = 0
    row_count: int = 0


class TableDetailOut(TableOut):
    columns: list[ColumnOut] = Field(default_factory=list)


class TablePage(BaseModel):
    items: list[TableOut]
    total: int
    limit: int
    offset: int


# --- Qatorlar -----------------------------------------------------------------


class RowCreate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class RowUpdate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    # Optimistik qulf: mos kelmasa 409
    expected_updated_at: datetime | None = None


class RowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    data: dict[str, Any]
    position: int | None
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class RowPage(BaseModel):
    items: list[RowOut]
    total: int
    limit: int
    offset: int


class RowBulkCreate(BaseModel):
    """CSV/ommaviy import — har bir element bitta qator `data` dict'i."""

    rows: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class RowBulkError(BaseModel):
    index: int
    errors: dict[str, str]


class RowBulkResult(BaseModel):
    created: int
    failed: int
    errors: list[RowBulkError] = Field(default_factory=list)
    items: list[RowOut] = Field(default_factory=list)


class RowRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_id: uuid.UUID
    action: str
    data: dict[str, Any] | None
    changed_by: uuid.UUID | None
    changed_at: datetime


# --- Yordamchi -----------------------------------------------------------------


class ReorderItem(BaseModel):
    id: uuid.UUID
    position: int = Field(ge=0)


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(min_length=1, max_length=200)


class DirectoryUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool
