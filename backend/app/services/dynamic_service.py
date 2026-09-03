"""Dinamik jadvallar uchun yordamchi funksiyalar: slug, ustun kaliti, tur o'zgarishi."""

import re
import secrets
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dynamic import ColumnType, DynamicRow, DynamicTable

_TRANSLIT = str.maketrans(
    {
        "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h", "ъ": "", "ь": "",
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh",
        "ы": "i", "э": "e", "ю": "yu", "я": "ya",
    }
)


def slugify(name: str) -> str:
    s = name.strip().lower().translate(_TRANSLIT)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:120] or f"jadval-{secrets.token_hex(3)}"


async def unique_slug(
    db: AsyncSession, section: str, name: str, *, exclude_id=None
) -> str:
    base = slugify(name)
    candidate = base
    n = 2
    while True:
        stmt = select(DynamicTable.id).where(
            DynamicTable.section == section, DynamicTable.slug == candidate
        )
        if exclude_id is not None:
            stmt = stmt.where(DynamicTable.id != exclude_id)
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if exists is None:
            return candidate
        candidate = f"{base}-{n}"[:130]
        n += 1


def new_column_key() -> str:
    return "c_" + secrets.token_hex(6)


# Tur o'zgarishi xavfsizmi? (bo'sh bo'lmagan jadvalda faqat shular ruxsat)
_SAFE_CHANGES: set[tuple[ColumnType, ColumnType]] = set()
for _t in ColumnType:
    _SAFE_CHANGES.add((_t, ColumnType.text))
    _SAFE_CHANGES.add((_t, ColumnType.long_text))
_SAFE_CHANGES.add((ColumnType.text, ColumnType.long_text))
_SAFE_CHANGES.add((ColumnType.long_text, ColumnType.text))


def type_change_needs_empty_table(old: ColumnType, new: ColumnType) -> bool:
    if old is new:
        return False
    return (old, new) not in _SAFE_CHANGES


async def table_has_rows(db: AsyncSession, table_id) -> bool:
    n = (
        await db.execute(
            select(func.count()).select_from(DynamicRow).where(DynamicRow.table_id == table_id)
        )
    ).scalar_one()
    return n > 0
