"""Dinamik jadval qator qiymatlarini tekshirish va normallashtirish.

Barcha tur-xavfsizligi shu yerda — DB darajasida emas. Har bir qiymat ustun
ta'rifiga (`DynamicColumn`) qarab tekshiriladi va standart ko'rinishga keltiriladi.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.models.dynamic import ColumnType, DynamicColumn

MAX_TEXT = 500
MAX_LONG_TEXT = 20_000
MAX_MULTI_SELECT = 100
MAX_OPTIONS = 200

_TRUE = {"true", "1", "yes", "on", "ha"}
_FALSE = {"false", "0", "no", "off", "yo'q", "yoq"}

_NEEDS_OPTIONS = {ColumnType.select, ColumnType.multi_select}
_NUMERIC_ONLY_KEYS = {"min", "max"}
_HEX_RE = None  # lazy


def _valid_color(c: object) -> bool:
    if not isinstance(c, str):
        return False
    import re

    return bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c))


def normalize_column_config(col_type: ColumnType, config: object) -> dict[str, Any]:
    """Ustun `config` ini tur bo'yicha tekshiradi/tozalaydi. Xato -> ValueError."""
    cfg: dict[str, Any] = dict(config) if isinstance(config, dict) else {}
    out: dict[str, Any] = {}

    if cfg.get("required") is not None:
        out["required"] = bool(cfg["required"])

    if col_type in _NEEDS_OPTIONS:
        raw_opts = cfg.get("options")
        if not isinstance(raw_opts, list) or not raw_opts:
            raise ValueError("select/multi_select ustuni uchun kamida bitta variant kerak")
        if len(raw_opts) > MAX_OPTIONS:
            raise ValueError(f"{MAX_OPTIONS} tadan ko'p variant bo'lmasligi kerak")
        seen_values: set[str] = set()
        options: list[dict[str, Any]] = []
        for o in raw_opts:
            if not isinstance(o, dict):
                raise ValueError("variant {value,label} ko'rinishida bo'lishi kerak")
            value = str(o.get("value", "")).strip()
            label = str(o.get("label", value)).strip() or value
            if not value:
                raise ValueError("variant qiymati bo'sh bo'lmasligi kerak")
            if len(value) > 60 or len(label) > 80:
                raise ValueError("variant qiymati/nomi juda uzun")
            if value in seen_values:
                raise ValueError(f"'{value}' varianti takrorlangan")
            seen_values.add(value)
            opt: dict[str, Any] = {"value": value, "label": label}
            if o.get("color") is not None:
                if not _valid_color(o["color"]):
                    raise ValueError("rang #RGB yoki #RRGGBB ko'rinishida bo'lishi kerak")
                opt["color"] = o["color"]
            options.append(opt)
        out["options"] = options
    else:
        if cfg.get("options"):
            raise ValueError("bu ustun turi variantlarni qo'llab-quvvatlamaydi")

    if col_type is ColumnType.number:
        for k in _NUMERIC_ONLY_KEYS:
            if cfg.get(k) is not None:
                try:
                    out[k] = float(cfg[k])
                except (TypeError, ValueError):
                    raise ValueError(f"{k} raqam bo'lishi kerak")
        if "min" in out and "max" in out and out["min"] > out["max"]:
            raise ValueError("min qiymati max dan katta bo'lmasligi kerak")
    elif any(cfg.get(k) is not None for k in _NUMERIC_ONLY_KEYS):
        raise ValueError("min/max faqat raqam ustunida ishlaydi")

    # default — turga mos bo'lishi kerak (dummy ustun orqali tekshiramiz)
    if cfg.get("default") is not None:
        probe = _ProbeColumn(col_type, out)
        try:
            out["default"] = coerce_value(probe, cfg["default"], known_user_ids=set())
        except ValueError as exc:
            # user turidagi default'ni mavjudlik tekshiruvisiz qabul qilamiz
            if col_type is ColumnType.user:
                out["default"] = str(cfg["default"])
            else:
                raise ValueError(f"standart qiymat noto'g'ri: {exc}")

    return out


class _ProbeColumn:
    """`coerce_value` ni config tekshiruvida qayta ishlatish uchun yengil ustun."""

    __slots__ = ("type", "config", "label")

    def __init__(self, col_type: ColumnType, config: dict[str, Any]) -> None:
        self.type = col_type
        self.config = config
        self.label = "default"


class RowValidationError(Exception):
    """Qator qiymatlari siyosatga mos kelmaganda. `errors` — ustun kaliti -> xabar."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _option_values(col: DynamicColumn) -> list[str]:
    return [str(o["value"]) for o in (col.config or {}).get("options", [])]


def collect_user_refs(columns: list[DynamicColumn], payload: dict[str, Any]) -> set[uuid.UUID]:
    """Payload ichidagi barcha `user` turidagi qiymatlarni UUID sifatida yig'adi."""
    by_key = {c.key: c for c in columns}
    out: set[uuid.UUID] = set()
    for key, raw in payload.items():
        col = by_key.get(key)
        if col is None or col.type is not ColumnType.user or _is_blank(raw):
            continue
        try:
            out.add(uuid.UUID(str(raw)))
        except (ValueError, TypeError):
            continue
    return out


def coerce_value(col: DynamicColumn, raw: Any, *, known_user_ids: set[uuid.UUID]) -> Any:
    """Bitta qiymatni tekshiradi/normallashtiradi. Xato bo'lsa `ValueError`."""
    t = col.type

    if _is_blank(raw):
        return None

    if t in (ColumnType.text, ColumnType.long_text):
        if not isinstance(raw, (str, int, float)):
            raise ValueError("matn qiymati kutilgan")
        s = str(raw).strip()
        limit = MAX_TEXT if t is ColumnType.text else MAX_LONG_TEXT
        if len(s) > limit:
            raise ValueError(f"matn {limit} belgidan uzun bo'lmasligi kerak")
        return s or None

    if t is ColumnType.number:
        if isinstance(raw, bool):
            raise ValueError("raqam qiymati kutilgan")
        try:
            num = float(raw)
        except (TypeError, ValueError):
            raise ValueError("raqam qiymati kutilgan")
        if math.isnan(num) or math.isinf(num):
            raise ValueError("raqam chekli bo'lishi kerak")
        cfg = col.config or {}
        if cfg.get("min") is not None and num < float(cfg["min"]):
            raise ValueError(f"qiymat {cfg['min']} dan kichik bo'lmasligi kerak")
        if cfg.get("max") is not None and num > float(cfg["max"]):
            raise ValueError(f"qiymat {cfg['max']} dan katta bo'lmasligi kerak")
        return int(num) if num.is_integer() else num

    if t is ColumnType.boolean:
        if isinstance(raw, bool):
            return raw
        s = str(raw).strip().lower()
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
        raise ValueError("mantiqiy (ha/yo'q) qiymat kutilgan")

    if t is ColumnType.date:
        try:
            d = date.fromisoformat(str(raw)[:10])
        except ValueError:
            raise ValueError("sana YYYY-MM-DD ko'rinishida bo'lishi kerak")
        return d.isoformat()

    if t is ColumnType.datetime:
        s = str(raw).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            raise ValueError("sana-vaqt ISO 8601 ko'rinishida bo'lishi kerak")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    if t is ColumnType.select:
        opts = _option_values(col)
        val = str(raw)
        if val not in opts:
            raise ValueError("tanlangan variant ustun ro'yxatida yo'q")
        return val

    if t is ColumnType.multi_select:
        if not isinstance(raw, (list, tuple)):
            raise ValueError("bir nechta variant ro'yxati kutilgan")
        opts = set(_option_values(col))
        seen: list[str] = []
        for item in raw:
            v = str(item)
            if v not in opts:
                raise ValueError(f"'{v}' varianti ustun ro'yxatida yo'q")
            if v not in seen:
                seen.append(v)
        if len(seen) > MAX_MULTI_SELECT:
            raise ValueError(f"{MAX_MULTI_SELECT} tadan ko'p variant tanlab bo'lmaydi")
        return seen

    if t is ColumnType.user:
        try:
            uid = uuid.UUID(str(raw))
        except (ValueError, TypeError):
            raise ValueError("foydalanuvchi identifikatori noto'g'ri")
        if uid not in known_user_ids:
            raise ValueError("bunday foydalanuvchi mavjud emas")
        return str(uid)

    raise ValueError("noma'lum ustun turi")  # pragma: no cover


def validate_row_data(
    columns: list[DynamicColumn],
    payload: dict[str, Any],
    *,
    mode: str,  # "create" | "update"
    existing: dict[str, Any] | None,
    known_user_ids: set[uuid.UUID],
) -> dict[str, Any]:
    """To'liq qatorni tekshiradi va saqlash uchun tayyor `data` dict qaytaradi.

    create: barcha ustunlar ko'rib chiqiladi, majburiylar tekshiriladi, default'lar qo'llanadi.
    update: faqat berilgan kalitlar tekshiriladi va mavjud `data` ustiga birlashtiriladi.
    """
    by_key = {c.key: c for c in columns}
    errors: dict[str, str] = {}

    unknown = set(payload) - set(by_key)
    for k in unknown:
        errors[k] = "noma'lum ustun"

    result: dict[str, Any] = dict(existing or {}) if mode == "update" else {}

    keys_to_check = set(payload) if mode == "update" else set(by_key)
    for key in keys_to_check:
        if key in unknown:
            continue
        col = by_key[key]
        provided = key in payload
        raw = payload.get(key)

        if not provided and mode == "create":
            default = (col.config or {}).get("default")
            raw = default
            provided = default is not None

        if _is_blank(raw):
            if (col.config or {}).get("required"):
                errors[key] = f"'{col.label}' majburiy"
            else:
                result[key] = None
            continue

        try:
            result[key] = coerce_value(col, raw, known_user_ids=known_user_ids)
        except ValueError as exc:
            errors[key] = str(exc)

    # update rejimida majburiy ustun bo'shatilgan bo'lsa
    if mode == "update":
        for key in payload:
            if key in by_key and (by_key[key].config or {}).get("required") and result.get(key) is None:
                errors.setdefault(key, f"'{by_key[key].label}' majburiy")

    if errors:
        raise RowValidationError(errors)

    # faqat mavjud ustun kalitlarini qoldiramiz (yetim kalitlar bo'lmasin)
    return {k: v for k, v in result.items() if k in by_key}
