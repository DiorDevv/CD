"""Dinamik jadval qator qiymatlarini tekshirish va normallashtirish.

Barcha tur-xavfsizligi shu yerda — DB darajasida emas. Har bir qiymat ustun
ta'rifiga (`DynamicColumn`) qarab tekshiriladi va standart ko'rinishga keltiriladi.
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.models.dynamic import ColumnType, DynamicColumn

MAX_TEXT = 500
MAX_LONG_TEXT = 20_000

# Ustunga bog'liq bo'lmagan qator holati kaliti ("bajarildi" belgisi)
ROW_DONE_KEY = "__done"
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

    # Ustunning ko'rsatiladigan kengligi (px) — turdan qat'i nazar
    if cfg.get("width") is not None:
        try:
            w = int(cfg["width"])
        except (TypeError, ValueError):
            raise ValueError("width butun son bo'lishi kerak")
        out["width"] = max(80, min(800, w))


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


def collect_user_values(columns: list[DynamicColumn], payload: dict[str, Any]) -> set[str]:
    """`user` ustunlaridagi barcha xom qiymatlar (UUID yoki username) — matn sifatida."""
    by_key = {c.key: c for c in columns}
    out: set[str] = set()
    for key, raw in payload.items():
        col = by_key.get(key)
        if col is None or col.type is not ColumnType.user or _is_blank(raw):
            continue
        out.add(str(raw).strip())
    return out


def _option_label_map(col: DynamicColumn) -> dict[str, str]:
    """label(lower) -> value — eksport label yozgani uchun importda ham tanish."""
    out: dict[str, str] = {}
    for o in (col.config or {}).get("options", []):
        lbl = str(o.get("label", "")).strip().lower()
        if lbl:
            out.setdefault(lbl, str(o["value"]))
    return out


def coerce_value(
    col: DynamicColumn,
    raw: Any,
    *,
    known_user_ids: set[uuid.UUID],
    known_usernames: dict[str, uuid.UUID] | None = None,
) -> Any:
    """Bitta qiymatni tekshiradi/normallashtiradi. Xato bo'lsa `ValueError`.

    Import/CSV uchun: select/multi_select variant **label**ini ham, `user`
    ustuni **username**ini ham qabul qiladi (eksport aynan shularni yozadi).
    """
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
            val = _option_label_map(col).get(val.strip().lower(), val)
        if val not in opts:
            raise ValueError("tanlangan variant ustun ro'yxatida yo'q")
        return val

    if t is ColumnType.multi_select:
        values = set(_option_values(col))
        by_label = _option_label_map(col)
        if isinstance(raw, (list, tuple)):
            items = [str(x).strip() for x in raw]
        elif isinstance(raw, str):
            # eksport "a, b" ko'rinishida yozadi; label ichida vergul bo'lsa
            # butun satr bitta variant bo'lishi mumkin
            if raw.strip().lower() in by_label or raw.strip() in values:
                items = [raw.strip()]
            else:
                items = [p.strip() for p in re.split(r"[,;\n|]", raw) if p.strip()]
        else:
            raise ValueError("bir nechta variant ro'yxati kutilgan")
        seen: list[str] = []
        for item in items:
            v = item if item in values else by_label.get(item.lower(), item)
            if v not in values:
                raise ValueError(f"'{item}' varianti ustun ro'yxatida yo'q")
            if v not in seen:
                seen.append(v)
        if len(seen) > MAX_MULTI_SELECT:
            raise ValueError(f"{MAX_MULTI_SELECT} tadan ko'p variant tanlab bo'lmaydi")
        return seen

    if t is ColumnType.user:
        s = str(raw).strip()
        uid: uuid.UUID | None
        try:
            uid = uuid.UUID(s)
        except (ValueError, TypeError):
            uid = None
        if uid is not None:
            if uid not in known_user_ids:
                raise ValueError("bunday foydalanuvchi mavjud emas")
            return str(uid)
        # UUID emas — username bo'lishi mumkin (eksport username yozadi)
        hit = (known_usernames or {}).get(s.lower())
        if hit is None:
            raise ValueError(f"foydalanuvchi topilmadi: {s}")
        return str(hit)

    raise ValueError("noma'lum ustun turi")  # pragma: no cover


def validate_row_data(
    columns: list[DynamicColumn],
    payload: dict[str, Any],
    *,
    mode: str,  # "create" | "update"
    existing: dict[str, Any] | None,
    known_user_ids: set[uuid.UUID],
    known_usernames: dict[str, uuid.UUID] | None = None,
) -> dict[str, Any]:
    """To'liq qatorni tekshiradi va saqlash uchun tayyor `data` dict qaytaradi.

    create: barcha ustunlar ko'rib chiqiladi, majburiylar tekshiriladi, default'lar qo'llanadi.
    update: faqat berilgan kalitlar tekshiriladi va mavjud `data` ustiga birlashtiriladi.
    """
    by_key = {c.key: c for c in columns}
    errors: dict[str, str] = {}

    # `__done` — ustunga bog'liq bo'lmagan qator holati ("bajarildi" belgisi).
    # Ustun ro'yxatida yo'q, lekin ruxsat etilgan va bool sifatida saqlanadi.
    unknown = set(payload) - set(by_key) - {ROW_DONE_KEY}
    for k in unknown:
        errors[k] = "noma'lum ustun"

    result: dict[str, Any] = dict(existing or {}) if mode == "update" else {}

    keys_to_check = set(payload) if mode == "update" else set(by_key)
    for key in keys_to_check:
        if key in unknown or key == ROW_DONE_KEY:
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
            result[key] = coerce_value(
                col, raw, known_user_ids=known_user_ids, known_usernames=known_usernames
            )
        except ValueError as exc:
            errors[key] = str(exc)

    # update rejimida majburiy ustun bo'shatilgan bo'lsa
    if mode == "update":
        for key in payload:
            if key in by_key and (by_key[key].config or {}).get("required") and result.get(key) is None:
                errors.setdefault(key, f"'{by_key[key].label}' majburiy")

    # `__done` qator holati — faqat true bo'lsa saqlanadi
    if ROW_DONE_KEY in payload:
        if payload[ROW_DONE_KEY]:
            result[ROW_DONE_KEY] = True
        else:
            result.pop(ROW_DONE_KEY, None)

    if errors:
        raise RowValidationError(errors)

    # faqat mavjud ustun kalitlari + `__done` qoladi (yetim kalitlar bo'lmasin)
    return {k: v for k, v in result.items() if k in by_key or k == ROW_DONE_KEY}
