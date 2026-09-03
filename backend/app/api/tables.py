"""Dinamik jadvallar API — foydalanuvchi o'zi tuzadigan jadval/ustun/qatorlar."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Numeric, Text, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    can_read_section,
    can_write_section,
    get_current_active_user,
    readable_sections,
)
from app.core.audit import write_audit
from app.database import get_db
from app.models.audit_log import AuditAction
from app.models.dynamic import (
    ColumnType,
    DynamicColumn,
    DynamicRow,
    DynamicRowRevision,
    DynamicTable,
    TableSection,
)
from app.models.user import User
from app.schemas.dynamic import (
    ColumnCreate,
    ColumnOut,
    ColumnUpdate,
    ReorderRequest,
    RowBulkCreate,
    RowBulkResult,
    RowCreate,
    RowOut,
    RowPage,
    RowRevisionOut,
    RowUpdate,
    TableCreate,
    TableDetailOut,
    TableOut,
    TablePage,
    TableUpdate,
)
from app.schemas.user import MessageOut
from app.services.dynamic_service import (
    new_column_key,
    table_has_rows,
    type_change_needs_empty_table,
    unique_slug,
)
from app.services.dynamic_values import (
    RowValidationError,
    collect_user_refs,
    normalize_column_config,
    validate_row_data,
)

router = APIRouter(prefix="/tables", tags=["tables"])


# --- Yordamchilar ------------------------------------------------------------


async def _load_table(db: AsyncSession, table_id: uuid.UUID) -> DynamicTable:
    res = await db.execute(
        select(DynamicTable)
        .where(DynamicTable.id == table_id)
        .options(selectinload(DynamicTable.columns))
    )
    table = res.scalar_one_or_none()
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jadval topilmadi")
    return table


def _guard_read(user: User, table: DynamicTable) -> None:
    if not can_read_section(user, table.section.value):
        # Ma'lumot chiqarmaslik uchun 404
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jadval topilmadi")


def _guard_write(user: User, section: str) -> None:
    if not can_write_section(user, section):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu bo'lim uchun yozish ruxsati yo'q")


async def _counts(db: AsyncSession, table_ids: list[uuid.UUID]) -> tuple[dict, dict]:
    if not table_ids:
        return {}, {}
    col_rows = await db.execute(
        select(DynamicColumn.table_id, func.count())
        .where(DynamicColumn.table_id.in_(table_ids))
        .group_by(DynamicColumn.table_id)
    )
    row_rows = await db.execute(
        select(DynamicRow.table_id, func.count())
        .where(DynamicRow.table_id.in_(table_ids))
        .group_by(DynamicRow.table_id)
    )
    return dict(col_rows.all()), dict(row_rows.all())


def _table_out(table: DynamicTable, col_count: int, row_count: int) -> TableOut:
    return TableOut(
        **{
            "id": table.id,
            "section": table.section,
            "name": table.name,
            "slug": table.slug,
            "description": table.description,
            "position": table.position,
            "is_archived": table.is_archived,
            "created_by": table.created_by,
            "created_at": table.created_at,
            "updated_at": table.updated_at,
            "column_count": col_count,
            "row_count": row_count,
        }
    )


def _detail_out(table: DynamicTable, row_count: int) -> TableDetailOut:
    cols = sorted(table.columns, key=lambda c: c.position)
    return TableDetailOut(
        **_table_out(table, len(cols), row_count).model_dump(),
        columns=[ColumnOut.model_validate(c) for c in cols],
    )


async def _row_count(db: AsyncSession, table_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(DynamicRow).where(DynamicRow.table_id == table_id)
        )
    ).scalar_one()


def _revision(table_id, row_id, action: str, data, user_id) -> DynamicRowRevision:
    return DynamicRowRevision(
        table_id=table_id, row_id=row_id, action=action, data=data, changed_by=user_id
    )


async def _touch_table(db: AsyncSession, table_id: uuid.UUID) -> None:
    """Ustun yoki qator o'zgarganda jadvalning `updated_at` ini yangilaydi —
    ro'yxatda 'oxirgi o'zgarish' ma'noli bo'lishi uchun."""
    await db.execute(
        update(DynamicTable)
        .where(DynamicTable.id == table_id)
        .values(updated_at=datetime.now(timezone.utc))
    )


# --- Jadvallar ------------------------------------------------------------------


@router.get("", response_model=TablePage)
async def list_tables(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
    section: TableSection | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TablePage:
    allowed = readable_sections(user)
    if section is not None and section.value not in allowed:
        return TablePage(items=[], total=0, limit=limit, offset=offset)

    conds = [DynamicTable.section.in_([section.value] if section else allowed)]
    if not include_archived:
        conds.append(DynamicTable.is_archived.is_(False))

    base = select(DynamicTable)
    count_stmt = select(func.count()).select_from(DynamicTable)
    for c in conds:
        base = base.where(c)
        count_stmt = count_stmt.where(c)

    total = (await db.execute(count_stmt)).scalar_one()
    tables = (
        await db.execute(
            base.order_by(DynamicTable.position, DynamicTable.name).limit(limit).offset(offset)
        )
    ).scalars().all()

    col_counts, row_counts = await _counts(db, [t.id for t in tables])
    return TablePage(
        items=[_table_out(t, col_counts.get(t.id, 0), row_counts.get(t.id, 0)) for t in tables],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TableDetailOut, status_code=status.HTTP_201_CREATED)
async def create_table(
    payload: TableCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> TableDetailOut:
    _guard_write(user, payload.section.value)

    slug = await unique_slug(db, payload.section.value, payload.name)
    table = DynamicTable(
        section=payload.section,
        name=payload.name.strip(),
        slug=slug,
        description=(payload.description or None),
        created_by=user.id,
    )
    db.add(table)
    await db.flush()

    for i, col in enumerate(payload.columns):
        try:
            cfg = normalize_column_config(col.type, col.config)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"'{col.label}': {exc}")
        db.add(
            DynamicColumn(
                table_id=table.id,
                key=new_column_key(),
                label=col.label.strip(),
                type=col.type,
                config=cfg,
                position=col.position if col.position is not None else i,
            )
        )

    await write_audit(
        db,
        action=AuditAction.TABLE_CREATED,
        user_id=user.id,
        details={"table_id": str(table.id), "name": table.name, "section": table.section.value},
        request=request,
    )
    await db.commit()
    table = await _load_table(db, table.id)
    return _detail_out(table, 0)


@router.get("/{table_id}", response_model=TableDetailOut)
async def get_table(
    table_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> TableDetailOut:
    table = await _load_table(db, table_id)
    _guard_read(user, table)
    return _detail_out(table, await _row_count(db, table.id))


@router.patch("/{table_id}", response_model=TableDetailOut)
async def update_table(
    table_id: uuid.UUID,
    payload: TableUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> TableDetailOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)

    action = AuditAction.TABLE_UPDATED
    if payload.name is not None and payload.name.strip() != table.name:
        table.name = payload.name.strip()
        table.slug = await unique_slug(db, table.section.value, table.name, exclude_id=table.id)
    if payload.description is not None:
        table.description = payload.description or None
    if payload.position is not None:
        table.position = payload.position
    if payload.is_archived is not None and payload.is_archived != table.is_archived:
        table.is_archived = payload.is_archived
        action = AuditAction.TABLE_ARCHIVED if payload.is_archived else AuditAction.TABLE_RESTORED

    await write_audit(
        db,
        action=action,
        user_id=user.id,
        details={"table_id": str(table.id), "name": table.name},
        request=request,
    )
    await db.commit()
    table = await _load_table(db, table.id)
    return _detail_out(table, await _row_count(db, table.id))


@router.delete("/{table_id}", response_model=MessageOut)
async def delete_table(
    table_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MessageOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    if user.role.value != "super_admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Jadvalni butunlay o'chirishni faqat super admin bajaradi. Arxivga o'tkazing.",
        )
    name = table.name
    await write_audit(
        db,
        action=AuditAction.TABLE_DELETED,
        user_id=user.id,
        details={"table_id": str(table.id), "name": name, "section": table.section.value},
        request=request,
    )
    await db.delete(table)
    await db.commit()
    return MessageOut(detail=f"'{name}' jadvali o'chirildi")


# --- Ustunlar --------------------------------------------------------------


def _get_column(table: DynamicTable, cid: uuid.UUID) -> DynamicColumn:
    for c in table.columns:
        if c.id == cid:
            return c
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Ustun topilmadi")


@router.post("/{table_id}/columns", response_model=ColumnOut, status_code=status.HTTP_201_CREATED)
async def add_column(
    table_id: uuid.UUID,
    payload: ColumnCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ColumnOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    try:
        cfg = normalize_column_config(payload.type, payload.config)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    pos = payload.position
    if pos is None:
        pos = (max((c.position for c in table.columns), default=-1)) + 1

    col = DynamicColumn(
        table_id=table.id,
        key=new_column_key(),
        label=payload.label.strip(),
        type=payload.type,
        config=cfg,
        position=pos,
    )
    db.add(col)
    await write_audit(
        db,
        action=AuditAction.COLUMN_ADDED,
        user_id=user.id,
        details={"table_id": str(table.id), "label": col.label, "type": col.type.value},
        request=request,
    )
    await _touch_table(db, table.id)
    await db.commit()
    await db.refresh(col)
    return ColumnOut.model_validate(col)


@router.patch("/{table_id}/columns/{column_id}", response_model=ColumnOut)
async def update_column(
    table_id: uuid.UUID,
    column_id: uuid.UUID,
    payload: ColumnUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ColumnOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    col = _get_column(table, column_id)

    target_type = payload.type or col.type

    # Tur o'zgarishi
    if payload.type is not None and payload.type is not col.type:
        if type_change_needs_empty_table(col.type, payload.type) and await table_has_rows(db, table.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Bu tur o'zgarishini faqat qatorlar bo'sh bo'lganda qilish mumkin",
            )
        if payload.type in (ColumnType.select, ColumnType.multi_select) and payload.config is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Yangi tur uchun variantlar (config.options) berilishi kerak",
            )

    # config
    if payload.config is not None or payload.type is not None:
        raw_cfg = payload.config if payload.config is not None else col.config
        try:
            new_cfg = normalize_column_config(target_type, raw_cfg)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

        # Ishlatilayotgan select variantini olib tashlashga yo'l qo'ymaymiz
        if col.type in (ColumnType.select, ColumnType.multi_select) and target_type == col.type:
            old_values = {o["value"] for o in (col.config or {}).get("options", [])}
            new_values = {o["value"] for o in new_cfg.get("options", [])}
            removed = old_values - new_values
            for val in removed:
                if col.type is ColumnType.select:
                    cnt = (
                        await db.execute(
                            select(func.count())
                            .select_from(DynamicRow)
                            .where(
                                DynamicRow.table_id == table.id,
                                DynamicRow.data[col.key].astext == val,
                            )
                        )
                    ).scalar_one()
                else:
                    cnt = (
                        await db.execute(
                            select(func.count())
                            .select_from(DynamicRow)
                            .where(
                                DynamicRow.table_id == table.id,
                                DynamicRow.data[col.key].contains([val]),
                            )
                        )
                    ).scalar_one()
                if cnt:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        f"'{val}' varianti {cnt} ta qatorda ishlatilmoqda — avval ularni o'zgartiring",
                    )
        col.config = new_cfg

    if payload.type is not None:
        col.type = payload.type
    if payload.label is not None:
        col.label = payload.label.strip()
    if payload.position is not None:
        col.position = payload.position

    await write_audit(
        db,
        action=AuditAction.COLUMN_UPDATED,
        user_id=user.id,
        details={"table_id": str(table.id), "column_id": str(col.id), "label": col.label},
        request=request,
    )
    await _touch_table(db, table.id)
    await db.commit()
    await db.refresh(col)
    return ColumnOut.model_validate(col)


@router.delete("/{table_id}/columns/{column_id}", response_model=MessageOut)
async def delete_column(
    table_id: uuid.UUID,
    column_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MessageOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    col = _get_column(table, column_id)
    key = col.key

    # Barcha qatorlardan kalitni atomik olib tashlaymiz
    await db.execute(
        update(DynamicRow)
        .where(DynamicRow.table_id == table.id)
        .values(data=DynamicRow.data.op("-")(key))
    )
    await db.delete(col)
    await write_audit(
        db,
        action=AuditAction.COLUMN_DELETED,
        user_id=user.id,
        details={"table_id": str(table.id), "label": col.label},
        request=request,
    )
    await _touch_table(db, table.id)
    await db.commit()
    return MessageOut(detail=f"'{col.label}' ustuni o'chirildi")


@router.post("/{table_id}/columns/reorder", response_model=list[ColumnOut])
async def reorder_columns(
    table_id: uuid.UUID,
    payload: ReorderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[ColumnOut]:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    by_id = {c.id: c for c in table.columns}
    if {i.id for i in payload.items} - set(by_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Noma'lum ustun identifikatori")
    for item in payload.items:
        by_id[item.id].position = item.position
    await _touch_table(db, table.id)
    await db.commit()
    table = await _load_table(db, table.id)
    return [ColumnOut.model_validate(c) for c in sorted(table.columns, key=lambda c: c.position)]


# --- Qatorlar -----------------------------------------------------------------


def _sort_clause(sort: str | None, columns: list[DynamicColumn]):
    if not sort:
        return [DynamicRow.position.asc().nullslast(), DynamicRow.created_at.asc()]
    key, _, direction = sort.partition(":")
    col = next((c for c in columns if c.key == key), None)
    if col is None:
        return [DynamicRow.created_at.asc()]
    expr = DynamicRow.data[col.key].astext
    if col.type is ColumnType.number:
        expr = cast(DynamicRow.data[col.key].astext, Numeric)
    ordering = expr.desc() if direction.lower() == "desc" else expr.asc()
    return [ordering.nullslast(), DynamicRow.created_at.asc()]


@router.get("/{table_id}/rows", response_model=RowPage)
async def list_rows(
    table_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=200),
) -> RowPage:
    table = await _load_table(db, table_id)
    _guard_read(user, table)

    base = select(DynamicRow).where(DynamicRow.table_id == table.id)
    count_stmt = select(func.count()).select_from(DynamicRow).where(DynamicRow.table_id == table.id)
    if q:
        needle = f"%{q.strip()}%"
        base = base.where(cast(DynamicRow.data, Text).ilike(needle))
        count_stmt = count_stmt.where(cast(DynamicRow.data, Text).ilike(needle))

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(*_sort_clause(sort, table.columns)).limit(limit).offset(offset)
        )
    ).scalars().all()
    return RowPage(
        items=[RowOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _known_user_ids(db: AsyncSession, ids: set[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    res = await db.execute(select(User.id).where(User.id.in_(ids)))
    return set(res.scalars().all())


@router.post("/{table_id}/rows", response_model=RowOut, status_code=status.HTTP_201_CREATED)
async def create_row(
    table_id: uuid.UUID,
    payload: RowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> RowOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    if table.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Arxivlangan jadvalga qator qo'shib bo'lmaydi")

    refs = collect_user_refs(table.columns, payload.data)
    known = await _known_user_ids(db, refs)
    try:
        data = validate_row_data(
            table.columns, payload.data, mode="create", existing=None, known_user_ids=known
        )
    except RowValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors})

    row = DynamicRow(table_id=table.id, data=data, created_by=user.id, updated_by=user.id)
    db.add(row)
    await db.flush()
    db.add(_revision(table.id, row.id, "create", data, user.id))
    await _touch_table(db, table.id)
    await db.commit()
    await db.refresh(row)
    return RowOut.model_validate(row)


@router.post(
    "/{table_id}/rows/bulk",
    response_model=RowBulkResult,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_rows(
    table_id: uuid.UUID,
    payload: RowBulkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> RowBulkResult:
    """CSV/ommaviy import — yaroqli qatorlarni qo'shadi, xatolilarni indeks bilan qaytaradi."""
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    if table.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Arxivlangan jadvalga qator qo'shib bo'lmaydi")

    all_refs: set[uuid.UUID] = set()
    for raw in payload.rows:
        all_refs |= collect_user_refs(table.columns, raw)
    known = await _known_user_ids(db, all_refs)

    good: list[dict] = []
    errors: list[dict] = []
    for i, raw in enumerate(payload.rows):
        try:
            good.append(
                validate_row_data(
                    table.columns, raw, mode="create", existing=None, known_user_ids=known
                )
            )
        except RowValidationError as exc:
            errors.append({"index": i, "errors": exc.errors})

    created_rows: list[DynamicRow] = []
    for data in good:
        row = DynamicRow(table_id=table.id, data=data, created_by=user.id, updated_by=user.id)
        db.add(row)
        created_rows.append(row)
    await db.flush()
    for row in created_rows:
        db.add(_revision(table.id, row.id, "create", row.data, user.id))
    if created_rows:
        await _touch_table(db, table.id)
    await db.commit()
    for row in created_rows:
        await db.refresh(row)

    return RowBulkResult(
        created=len(created_rows),
        failed=len(errors),
        errors=errors,
        items=[RowOut.model_validate(r) for r in created_rows],
    )


@router.patch("/{table_id}/rows/{row_id}", response_model=RowOut)
async def update_row(
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    payload: RowUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> RowOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    if table.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Arxivlangan jadval tahrirlab bo'lmaydi")

    row = await db.get(DynamicRow, row_id)
    if row is None or row.table_id != table.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qator topilmadi")

    if payload.expected_updated_at is not None:
        exp = payload.expected_updated_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if abs((row.updated_at - exp).total_seconds()) > 0.001:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Bu qatorni boshqa birov o'zgartirdi. Sahifani yangilang.",
            )

    refs = collect_user_refs(table.columns, payload.data)
    known = await _known_user_ids(db, refs)
    try:
        data = validate_row_data(
            table.columns, payload.data, mode="update", existing=row.data, known_user_ids=known
        )
    except RowValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors})

    row.data = data
    row.updated_by = user.id
    db.add(_revision(table.id, row.id, "update", data, user.id))
    await _touch_table(db, table.id)
    await db.commit()
    await db.refresh(row)
    return RowOut.model_validate(row)


@router.delete("/{table_id}/rows/{row_id}", response_model=MessageOut)
async def delete_row(
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MessageOut:
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    row = await db.get(DynamicRow, row_id)
    if row is None or row.table_id != table.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qator topilmadi")
    db.add(_revision(table.id, row.id, "delete", dict(row.data), user.id))
    await db.delete(row)
    await _touch_table(db, table.id)
    await db.commit()
    return MessageOut(detail="Qator o'chirildi")


@router.post("/{table_id}/rows/{row_id}/revisions/{revision_id}/restore", response_model=RowOut)
async def restore_revision(
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    revision_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> RowOut:
    """Qatorni tanlangan reviziyadagi holatga qaytaradi (joriy ustunlarга qayta tekshiriladi)."""
    table = await _load_table(db, table_id)
    _guard_write(user, table.section.value)
    if table.is_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, "Arxivlangan jadval tahrirlab bo'lmaydi")

    row = await db.get(DynamicRow, row_id)
    if row is None or row.table_id != table.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qator topilmadi")

    rev = await db.get(DynamicRowRevision, revision_id)
    if rev is None or rev.row_id != row_id or rev.table_id != table.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reviziya topilmadi")
    if rev.data is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bu reviziyada saqlangan ma'lumot yo'q")

    refs = collect_user_refs(table.columns, rev.data)
    known = await _known_user_ids(db, refs)
    try:
        data = validate_row_data(
            table.columns, rev.data, mode="create", existing=None, known_user_ids=known
        )
    except RowValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": exc.errors})

    row.data = data
    row.updated_by = user.id
    db.add(_revision(table.id, row.id, "update", data, user.id))
    await _touch_table(db, table.id)
    await db.commit()
    await db.refresh(row)
    return RowOut.model_validate(row)


@router.get("/{table_id}/rows/{row_id}/revisions", response_model=list[RowRevisionOut])
async def list_row_revisions(
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[RowRevisionOut]:
    table = await _load_table(db, table_id)
    _guard_read(user, table)
    res = await db.execute(
        select(DynamicRowRevision)
        .where(
            DynamicRowRevision.table_id == table.id,
            DynamicRowRevision.row_id == row_id,
        )
        .order_by(DynamicRowRevision.changed_at.desc())
        .limit(100)
    )
    return [RowRevisionOut.model_validate(r) for r in res.scalars().all()]
