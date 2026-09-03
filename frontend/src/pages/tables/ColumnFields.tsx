import { useRef, useState } from "react";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import type { ColumnType, SelectOption } from "@/lib/types";
import {
  COLUMN_TYPES,
  HAS_OPTIONS,
  SUPPORTS_DEFAULT,
  optionColor,
  toOptionValue,
  type ColumnDraft,
} from "@/lib/dynamic";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface Props {
  draft: ColumnDraft;
  onChange: (patch: Partial<ColumnDraft>) => void;
  /** tahrirlashda mavjud ustun turi (tur o'zgarishi ogohlantirishi uchun) */
  originalType?: ColumnType;
  /** kompakt ko'rinish (jadval yaratish oynasidagi ro'yxat uchun) */
  compact?: boolean;
}

export function ColumnFields({ draft, onChange, originalType, compact }: Props) {
  const dragIdx = useRef<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  function setOption(i: number, patch: Partial<SelectOption>) {
    onChange({
      options: draft.options.map((o, idx) => (idx === i ? { ...o, ...patch } : o)),
    });
  }
  function addOption() {
    onChange({
      options: [
        ...draft.options,
        {
          value: "",
          label: `Variant ${draft.options.length + 1}`,
          color: optionColor(draft.options.length),
        },
      ],
    });
  }
  function removeOption(i: number) {
    onChange({ options: draft.options.filter((_, idx) => idx !== i) });
  }
  function reorderOption(from: number, to: number) {
    if (from === to) return;
    const next = [...draft.options];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    onChange({ options: next });
  }

  function changeType(type: ColumnType) {
    onChange({
      type,
      default: type === "boolean" ? false : "",
      ...(HAS_OPTIONS.has(type) ? {} : { options: [] }),
    });
  }

  return (
    <div className="space-y-3.5">
      <div>
        <Label>Ustun nomi</Label>
        <Input
          value={draft.label}
          onChange={(e) => onChange({ label: e.target.value })}
          maxLength={120}
          placeholder="masalan: Sarlavha"
          autoFocus={!compact}
        />
      </div>

      <div>
        <Label>Tur</Label>
        <div className={cn("grid gap-1.5", compact ? "grid-cols-3" : "grid-cols-3 sm:grid-cols-4")}>
          {COLUMN_TYPES.map((t) => {
            const on = draft.type === t.value;
            return (
              <button
                key={t.value}
                type="button"
                onClick={() => changeType(t.value)}
                title={t.hint}
                aria-pressed={on}
                className={cn(
                  "flex items-center gap-1.5 rounded-md border px-2 py-2 text-2xs font-medium transition-all",
                  on
                    ? "border-accent bg-accent-soft text-content"
                    : "border-line-strong text-content-muted hover:border-line hover:text-content",
                )}
              >
                <t.icon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {originalType && originalType !== draft.type && (
        <p className="rounded-md border border-warning/30 bg-warning/10 px-2.5 py-1.5 text-2xs text-warning">
          Turni o'zgartirish — jadvalda qatorlar bo'lsa faqat ba'zi o'tishlar
          ruxsat etiladi (aks holda 409 xato).
        </p>
      )}

      {HAS_OPTIONS.has(draft.type) && (
        <div>
          <Label>Variantlar</Label>
          {draft.options.length === 0 && (
            <p className="mb-1.5 rounded-md border border-dashed border-line-strong py-2 text-center text-2xs text-content-faint">
              Kamida bitta variant kerak
            </p>
          )}
          <div className="space-y-1.5">
            {draft.options.map((o, i) => (
              <div
                key={i}
                draggable
                onDragStart={() => (dragIdx.current = i)}
                onDragEnter={() => setDragOver(i)}
                onDragOver={(e) => e.preventDefault()}
                onDragEnd={() => {
                  if (dragIdx.current !== null && dragOver !== null) {
                    reorderOption(dragIdx.current, dragOver);
                  }
                  dragIdx.current = null;
                  setDragOver(null);
                }}
                className={cn(
                  "flex items-center gap-1.5 rounded-md ring-1 ring-transparent transition-shadow",
                  dragOver === i && "ring-accent",
                )}
              >
                <GripVertical className="h-3.5 w-3.5 shrink-0 cursor-grab text-content-faint active:cursor-grabbing" />
                <input
                  type="color"
                  value={o.color ?? "#64748b"}
                  onChange={(e) => setOption(i, { color: e.target.value })}
                  className="h-8 w-8 shrink-0 cursor-pointer rounded border border-line-strong bg-transparent"
                  title="Rang"
                />
                <Input
                  value={o.label}
                  onChange={(e) => {
                    const label = e.target.value;
                    setOption(i, { label, ...(o.value ? {} : { value: "" }) });
                  }}
                  onBlur={() => {
                    if (!o.value && o.label.trim()) {
                      setOption(i, { value: toOptionValue(o.label) });
                    }
                  }}
                  placeholder="Ko'rinadigan nom"
                  className="h-8"
                />
                <Input
                  value={o.value}
                  onChange={(e) => setOption(i, { value: e.target.value })}
                  placeholder="qiymat"
                  className="h-8 w-24 font-mono text-xs"
                  title="Ichki (mashina) qiymati — o'zgartirmaslik tavsiya etiladi"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-content-faint hover:text-danger"
                  onClick={() => removeOption(i)}
                  aria-label="Variantni o'chirish"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={addOption}
          >
            <Plus className="h-3.5 w-3.5" />
            Variant qo'shish
          </Button>
        </div>
      )}

      {draft.type === "number" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Minimal</Label>
            <Input
              type="number"
              value={draft.min}
              onChange={(e) => onChange({ min: e.target.value })}
              placeholder="—"
            />
          </div>
          <div>
            <Label>Maksimal</Label>
            <Input
              type="number"
              value={draft.max}
              onChange={(e) => onChange({ max: e.target.value })}
              placeholder="—"
            />
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        {SUPPORTS_DEFAULT.has(draft.type) && (
          <DefaultField draft={draft} onChange={onChange} />
        )}
        <label className="flex h-10 items-center gap-2 text-sm text-content-muted">
          <input
            type="checkbox"
            checked={draft.required}
            onChange={(e) => onChange({ required: e.target.checked })}
            className="h-3.5 w-3.5 rounded border-line-strong accent-[hsl(var(--accent))]"
          />
          Majburiy maydon
        </label>
      </div>
    </div>
  );
}

function DefaultField({
  draft,
  onChange,
}: {
  draft: ColumnDraft;
  onChange: (patch: Partial<ColumnDraft>) => void;
}) {
  const base =
    "flex h-10 w-full rounded-md border border-line-strong bg-surface-raised px-3 text-sm text-content outline-none focus:border-accent";

  if (draft.type === "boolean") {
    return (
      <label className="flex h-10 items-center gap-2 text-sm text-content-muted">
        <input
          type="checkbox"
          checked={draft.default === true}
          onChange={(e) => onChange({ default: e.target.checked })}
          className="h-3.5 w-3.5 rounded border-line-strong accent-[hsl(var(--accent))]"
        />
        Standart: belgilangan
      </label>
    );
  }

  const val = typeof draft.default === "string" ? draft.default : "";
  return (
    <div className="min-w-[160px] flex-1">
      <Label>Standart qiymat</Label>
      {draft.type === "select" ? (
        <select
          value={val}
          onChange={(e) => onChange({ default: e.target.value })}
          className={base}
        >
          <option value="">— yo'q —</option>
          {draft.options.map((o, i) => (
            <option key={i} value={o.value || toOptionValue(o.label)}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={draft.type === "number" ? "number" : draft.type === "date" ? "date" : "text"}
          value={val}
          onChange={(e) => onChange({ default: e.target.value })}
          placeholder="— yo'q —"
          className={base}
        />
      )}
    </div>
  );
}
