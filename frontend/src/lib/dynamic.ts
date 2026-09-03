import {
  Calendar,
  CalendarClock,
  CheckSquare,
  Hash,
  List,
  ListChecks,
  Type,
  AlignLeft,
  User as UserIcon,
  type LucideIcon,
} from "lucide-react";
import type { ColumnType, DynamicColumn, SelectOption } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export interface ColumnTypeMeta {
  value: ColumnType;
  label: string;
  icon: LucideIcon;
  hint: string;
}

export const COLUMN_TYPES: ColumnTypeMeta[] = [
  { value: "text", label: "Matn", icon: Type, hint: "Bir qatorli matn" },
  { value: "long_text", label: "Uzun matn", icon: AlignLeft, hint: "Ko'p qatorli matn" },
  { value: "number", label: "Raqam", icon: Hash, hint: "Butun yoki kasr son" },
  { value: "boolean", label: "Ha/Yo'q", icon: CheckSquare, hint: "Belgilash katakchasi" },
  { value: "date", label: "Sana", icon: Calendar, hint: "Kun (YYYY-MM-DD)" },
  { value: "datetime", label: "Sana-vaqt", icon: CalendarClock, hint: "Kun va vaqt" },
  { value: "select", label: "Tanlov", icon: List, hint: "Ro'yxatdan bittasi" },
  { value: "multi_select", label: "Ko'p tanlov", icon: ListChecks, hint: "Ro'yxatdan bir nechtasi" },
  { value: "user", label: "Foydalanuvchi", icon: UserIcon, hint: "Platformadagi foydalanuvchi" },
];

const TYPE_META = new Map(COLUMN_TYPES.map((t) => [t.value, t]));

export function typeMeta(type: ColumnType): ColumnTypeMeta {
  return TYPE_META.get(type) ?? COLUMN_TYPES[0];
}

/** Tanlov varianti qiymati uchun barqaror kalit (label'dan). */
export function toOptionValue(label: string): string {
  const s = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return s || `opt_${Math.random().toString(36).slice(2, 7)}`;
}

/** Katak qiymatini matn ko'rinishida (qidiruv/ko'rsatish uchun). */
export function cellText(
  col: DynamicColumn,
  value: unknown,
  usernameById?: Map<string, string>,
): string {
  if (value === null || value === undefined || value === "") return "";
  switch (col.type) {
    case "boolean":
      return value ? "Ha" : "Yo'q";
    case "datetime":
      return formatDateTime(String(value));
    case "select": {
      const opt = col.config.options?.find((o) => o.value === value);
      return opt?.label ?? String(value);
    }
    case "multi_select": {
      const arr = Array.isArray(value) ? value : [];
      return arr
        .map((v) => col.config.options?.find((o) => o.value === v)?.label ?? String(v))
        .join(", ");
    }
    case "user":
      return usernameById?.get(String(value)) ?? "(noma'lum)";
    default:
      return String(value);
  }
}

const SWATCHES = [
  "#4f7cff",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#a855f7",
  "#14b8a6",
  "#ec4899",
  "#64748b",
];

export function optionColor(index: number): string {
  return SWATCHES[index % SWATCHES.length];
}

export const COLOR_SWATCHES = SWATCHES;

// ---------------------------------------------------------------------------
// Ustun konstruktori (yaratish + tahrirlash uchun umumiy qoralama)
// ---------------------------------------------------------------------------

export const HAS_OPTIONS = new Set<ColumnType>(["select", "multi_select"]);
/** Standart qiymat (default) qo'llab-quvvatlanadigan turlar. */
export const SUPPORTS_DEFAULT = new Set<ColumnType>([
  "text",
  "long_text",
  "number",
  "boolean",
  "date",
  "select",
]);

export interface ColumnDraft {
  /** ro'yxat kalitlari uchun mijoz tomonidagi id */
  uid: string;
  label: string;
  type: ColumnType;
  required: boolean;
  min: string;
  max: string;
  options: SelectOption[];
  /** turga qarab: string | boolean | "" */
  default: string | boolean;
}

let _uid = 0;
export function newColumnDraft(type: ColumnType = "text"): ColumnDraft {
  _uid += 1;
  return {
    uid: `d${Date.now().toString(36)}_${_uid}`,
    label: "",
    type,
    required: false,
    min: "",
    max: "",
    options: [],
    default: type === "boolean" ? false : "",
  };
}

export function columnToDraft(col: DynamicColumn): ColumnDraft {
  _uid += 1;
  const cfg = col.config ?? {};
  return {
    uid: `e${col.id}_${_uid}`,
    label: col.label,
    type: col.type,
    required: !!cfg.required,
    min: cfg.min != null ? String(cfg.min) : "",
    max: cfg.max != null ? String(cfg.max) : "",
    options: cfg.options ? cfg.options.map((o) => ({ ...o })) : [],
    default:
      col.type === "boolean"
        ? cfg.default === true
        : cfg.default != null
          ? String(cfg.default)
          : "",
  };
}

/** Qoralamani backend `{label,type,config}` ko'rinishiga aylantiradi. Xato -> `Error`. */
export function draftToColumnPayload(d: ColumnDraft): {
  label: string;
  type: ColumnType;
  config: Record<string, unknown>;
} {
  const label = d.label.trim();
  if (!label) throw new Error("Ustun nomi bo'sh bo'lmasligi kerak");

  const config: Record<string, unknown> = {};
  if (d.required) config.required = true;

  if (HAS_OPTIONS.has(d.type)) {
    if (d.options.length === 0) {
      throw new Error(`"${label}": kamida bitta variant qo'shing`);
    }
    const seen = new Set<string>();
    config.options = d.options.map((o) => {
      const value = (o.value || toOptionValue(o.label)).trim();
      if (!value) throw new Error(`"${label}": variant qiymati bo'sh`);
      if (seen.has(value)) throw new Error(`"${label}": '${value}' varianti takrorlangan`);
      seen.add(value);
      return {
        value,
        label: o.label.trim() || value,
        ...(o.color ? { color: o.color } : {}),
      };
    });
  }

  if (d.type === "number") {
    if (d.min !== "") config.min = Number(d.min);
    if (d.max !== "") config.max = Number(d.max);
    if (d.min !== "" && d.max !== "" && Number(d.min) > Number(d.max)) {
      throw new Error(`"${label}": minimal qiymat maksimaldan katta bo'lmasligi kerak`);
    }
  }

  if (SUPPORTS_DEFAULT.has(d.type)) {
    if (d.type === "boolean") {
      if (d.default === true) config.default = true;
    } else if (typeof d.default === "string" && d.default.trim() !== "") {
      config.default =
        d.type === "number" ? Number(d.default) : d.default.trim();
    }
  }

  return { label, type: d.type, config };
}

/** Yangi qator uchun ustunning standart boshlang'ich qiymati. */
export function defaultCellValue(col: DynamicColumn): unknown {
  const dv = col.config?.default;
  if (dv !== undefined && dv !== null) return dv;
  return col.type === "boolean" ? false : "";
}

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------

function csvEscape(s: string): string {
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function rowsToCsv(
  columns: DynamicColumn[],
  rows: { data: Record<string, unknown> }[],
  usernameById?: Map<string, string>,
): string {
  const header = columns.map((c) => csvEscape(c.label)).join(",");
  const lines = rows.map((r) =>
    columns
      .map((c) => csvEscape(cellText(c, r.data?.[c.key], usernameById)))
      .join(","),
  );
  return [header, ...lines].join("\r\n");
}

/** Oddiy RFC-4180 CSV tahlilchisi (tirnoq ichidagi vergul/yangi qatorni qo'llaydi). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  const src = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (inQuotes) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((c) => c.trim() !== ""));
}

/** CSV matn qiymatini ustun turiga mos qiymatga aylantiradi (import uchun). */
export function csvValueToCell(col: DynamicColumn, raw: string): unknown {
  const s = raw.trim();
  if (s === "") return undefined;
  switch (col.type) {
    case "number": {
      const n = Number(s);
      return Number.isFinite(n) ? n : s;
    }
    case "boolean":
      return /^(1|true|ha|yes|on)$/i.test(s);
    case "select": {
      const o = col.config.options?.find(
        (x) => x.value === s || x.label.toLowerCase() === s.toLowerCase(),
      );
      return o?.value ?? s;
    }
    case "multi_select": {
      const parts = s.split(/[,;|]/).map((p) => p.trim()).filter(Boolean);
      return parts.map((p) => {
        const o = col.config.options?.find(
          (x) => x.value === p || x.label.toLowerCase() === p.toLowerCase(),
        );
        return o?.value ?? p;
      });
    }
    default:
      return s;
  }
}
