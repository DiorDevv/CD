"""SOC/DLP bo'lim paneli — topshiriqlar (personal/shared) + yig'ma statistika.

Topshiriqlar dinamik jadvallardan alohida yengil ro'yxat. Statistika esa
o'sha bo'limning dinamik jadvallari ustidan hisoblanadi.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import can_read_section, can_write_section, get_current_active_user
from app.database import get_db
from app.models.dynamic import (
    ColumnType,
    DynamicColumn,
    DynamicRow,
    DynamicRowRevision,
    DynamicTable,
)
from app.models.section_todo import SectionTodo, TodoScope
from app.models.user import User
from app.schemas.dynamic import ColumnValueCount
from app.schemas.section import (
    RecentChange,
    SectionSummaryOut,
    SectionTableStat,
    SectionTotals,
    TodoCreate,
    TodoOut,
    TodoUpdate,
    TrendPoint,
)
from app.schemas.user import MessageOut

router = APIRouter(prefix="/sections", tags=["sections"])

_SECTIONS = {"soc", "dlp"}
_STATS_ROW_CAP = 20_000
_DONE_COND = DynamicRow.data["__done"].astext == "true"


def _valid_section(section: str = Path(...)) -> str:
    if section not in _SECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bo'lim topilmadi")
    return section


def _guard_read(user: User, section: str) -> None:
    if not can_read_section(user, section):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bo'lim topilmadi")


def _guard_write(user: User, section: str) -> None:
    if not can_write_section(user, section):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu bo'lim uchun yozish ruxsati yo'q")


# --- Topshiriqlar -------------------------------------------------------------


def _todo_out(todo: SectionTodo, name: str | None) -> TodoOut:
    return TodoOut(
        **{
            "id": todo.id,
            "section": todo.section,
            "scope": todo.scope,
            "owner_id": todo.owner_id,
            "owner_name": name,
            "text": todo.text,
            "is_done": todo.is_done,
            "due_date": todo.due_date,
            "position": todo.position,
            "created_at": todo.created_at,
            "done_at": todo.done_at,
        }
    )


async def _names(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    res = await db.execute(select(User.id, User.username).where(User.id.in_(ids)))
    return {uid: name for uid, name in res.all()}


async def _get_todo(db: AsyncSession, section: str, todo_id: uuid.UUID) -> SectionTodo:
    todo = await db.get(SectionTodo, todo_id)
    if todo is None or todo.section != section:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topshiriq topilmadi")
    return todo


def _guard_todo_write(user: User, section: str, todo: SectionTodo) -> None:
    if todo.scope is TodoScope.personal:
        if todo.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Topshiriq topilmadi")
    else:
        _guard_write(user, section)


@router.get("/{section}/todos", response_model=list[TodoOut])
async def list_todos(
    section: str = Depends(_valid_section),
    scope: TodoScope = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[TodoOut]:
    _guard_read(user, section)
    stmt = select(SectionTodo).where(
        SectionTodo.section == section, SectionTodo.scope == scope
    )
    if scope is TodoScope.personal:
        stmt = stmt.where(SectionTodo.owner_id == user.id)
    stmt = stmt.order_by(
        SectionTodo.is_done.asc(), SectionTodo.position.asc(), SectionTodo.created_at.asc()
    )
    todos = list((await db.execute(stmt)).scalars().all())
    names = await _names(db, {t.owner_id for t in todos})
    return [_todo_out(t, names.get(t.owner_id)) for t in todos]


@router.post("/{section}/todos", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create_todo(
    payload: TodoCreate,
    section: str = Depends(_valid_section),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> TodoOut:
    _guard_read(user, section)
    if payload.scope is TodoScope.shared:
        _guard_write(user, section)

    max_pos = (
        await db.execute(
            select(func.coalesce(func.max(SectionTodo.position), 0)).where(
                SectionTodo.section == section,
                SectionTodo.scope == payload.scope,
                *(
                    [SectionTodo.owner_id == user.id]
                    if payload.scope is TodoScope.personal
                    else []
                ),
            )
        )
    ).scalar_one()

    todo = SectionTodo(
        section=section,
        scope=payload.scope,
        owner_id=user.id,
        text=payload.text.strip(),
        due_date=payload.due_date,
        position=max_pos + 1,
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return _todo_out(todo, user.username)


@router.patch("/{section}/todos/{todo_id}", response_model=TodoOut)
async def update_todo(
    payload: TodoUpdate,
    section: str = Depends(_valid_section),
    todo_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> TodoOut:
    _guard_read(user, section)
    todo = await _get_todo(db, section, todo_id)
    _guard_todo_write(user, section, todo)

    fields = payload.model_fields_set
    if "text" in fields and payload.text is not None:
        todo.text = payload.text.strip()
    if "due_date" in fields:
        todo.due_date = payload.due_date
    if "is_done" in fields and payload.is_done is not None:
        todo.is_done = payload.is_done
        todo.done_at = datetime.now(timezone.utc) if payload.is_done else None

    await db.commit()
    await db.refresh(todo)
    names = await _names(db, {todo.owner_id})
    return _todo_out(todo, names.get(todo.owner_id))


@router.delete("/{section}/todos/{todo_id}", response_model=MessageOut)
async def delete_todo(
    section: str = Depends(_valid_section),
    todo_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> MessageOut:
    _guard_read(user, section)
    todo = await _get_todo(db, section, todo_id)
    _guard_todo_write(user, section, todo)
    await db.delete(todo)
    await db.commit()
    return MessageOut(detail="Topshiriq o'chirildi")


# --- Yig'ma statistika ------------------------------------------------------


@router.get("/{section}/summary", response_model=SectionSummaryOut)
async def section_summary(
    section: str = Depends(_valid_section),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> SectionSummaryOut:
    _guard_read(user, section)

    tables = list(
        (
            await db.execute(
                select(DynamicTable)
                .where(
                    DynamicTable.section == section, DynamicTable.is_archived.is_(False)
                )
                .options(selectinload(DynamicTable.columns))
                .order_by(DynamicTable.position, DynamicTable.name)
            )
        ).scalars().all()
    )
    tids = [t.id for t in tables]

    row_counts: dict[uuid.UUID, int] = {}
    done_counts: dict[uuid.UUID, int] = {}
    if tids:
        for tid, cnt in (
            await db.execute(
                select(DynamicRow.table_id, func.count())
                .where(DynamicRow.table_id.in_(tids))
                .group_by(DynamicRow.table_id)
            )
        ).all():
            row_counts[tid] = cnt
        for tid, cnt in (
            await db.execute(
                select(DynamicRow.table_id, func.count())
                .where(DynamicRow.table_id.in_(tids), _DONE_COND)
                .group_by(DynamicRow.table_id)
            )
        ).all():
            done_counts[tid] = cnt

    total_rows = sum(row_counts.values())
    total_done = sum(done_counts.values())

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    added_7d = 0
    if tids:
        added_7d = (
            await db.execute(
                select(func.count())
                .select_from(DynamicRow)
                .where(DynamicRow.table_id.in_(tids), DynamicRow.created_at >= week_ago)
            )
        ).scalar_one()

    totals = SectionTotals(
        tables=len(tables),
        rows=total_rows,
        done=total_done,
        open=total_rows - total_done,
        added_7d=added_7d,
    )

    # Har jadval uchun birinchi select/multi_select ustun bo'yicha taqsimot
    table_stats: list[SectionTableStat] = []
    for t in tables:
        rc = row_counts.get(t.id, 0)
        breakdown_label: str | None = None
        entries: list[ColumnValueCount] = []
        pick = next(
            (
                c
                for c in sorted(t.columns, key=lambda c: c.position)
                if c.type in (ColumnType.select, ColumnType.multi_select)
            ),
            None,
        )
        if pick is not None and 0 < rc <= _STATS_ROW_CAP:
            datas = (
                await db.execute(
                    select(DynamicRow.data).where(DynamicRow.table_id == t.id)
                )
            ).scalars().all()
            counter: dict[str, int] = {}
            for data in datas:
                v = (data or {}).get(pick.key)
                if pick.type is ColumnType.multi_select:
                    for item in v if isinstance(v, list) else []:
                        counter[str(item)] = counter.get(str(item), 0) + 1
                elif v not in (None, ""):
                    counter[str(v)] = counter.get(str(v), 0) + 1
            if counter:
                opts = {str(o["value"]): o for o in (pick.config or {}).get("options", [])}
                for val, cnt in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
                    o = opts.get(val)
                    entries.append(
                        ColumnValueCount(
                            value=val,
                            label=str(o["label"]) if o else val,
                            count=cnt,
                            color=(o.get("color") if o else None),
                        )
                    )
                breakdown_label = pick.label
        table_stats.append(
            SectionTableStat(
                id=t.id,
                name=t.name,
                row_count=rc,
                done_count=done_counts.get(t.id, 0),
                updated_at=t.updated_at,
                breakdown_label=breakdown_label,
                breakdown=entries,
            )
        )

    # So'nggi o'zgarishlar
    recent: list[RecentChange] = []
    if tids:
        rev_rows = (
            await db.execute(
                select(DynamicRowRevision, DynamicTable.name)
                .join(DynamicTable, DynamicTable.id == DynamicRowRevision.table_id)
                .where(DynamicRowRevision.table_id.in_(tids))
                .order_by(DynamicRowRevision.changed_at.desc())
                .limit(20)
            )
        ).all()
        who = await _names(db, {r.changed_by for r, _ in rev_rows if r.changed_by})
        recent = [
            RecentChange(
                table_id=r.table_id,
                table_name=tname,
                row_id=r.row_id,
                action=r.action,
                changed_by=r.changed_by,
                changed_by_name=who.get(r.changed_by) if r.changed_by else None,
                changed_at=r.changed_at,
            )
            for r, tname in rev_rows
        ]

    # Trend — oxirgi 14 kun, kunlik yangi qatorlar
    trend: list[TrendPoint] = []
    if tids:
        since = datetime.now(timezone.utc) - timedelta(days=13)
        day_col = func.date_trunc("day", DynamicRow.created_at).label("d")
        rows = (
            await db.execute(
                select(day_col, func.count())
                .where(DynamicRow.table_id.in_(tids), DynamicRow.created_at >= since)
                .group_by(day_col)
                .order_by(day_col)
            )
        ).all()
        by_day = {
            (d.date() if isinstance(d, datetime) else d): cnt for d, cnt in rows
        }
        start = date.today() - timedelta(days=13)
        trend = [
            TrendPoint(day=start + timedelta(days=i), count=by_day.get(start + timedelta(days=i), 0))
            for i in range(14)
        ]

    return SectionSummaryOut(
        section=section, totals=totals, tables=table_stats, recent=recent, trend=trend
    )
