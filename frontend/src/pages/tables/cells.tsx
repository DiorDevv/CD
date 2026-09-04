import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { cellText } from "@/lib/dynamic";
import { formatDateTime, isoToLocalInput } from "@/lib/utils";
import type { DynamicColumn } from "@/lib/types";
import { Button } from "@/components/ui/button";

// ---------- Forma uslubidagi maydon (yangi qator oynasi + grid'da inline qo'shish) ----------

export function RowFieldInput({
  col,
  value,
  users,
  onChange,
  compact,
}: {
  col: DynamicColumn;
  value: unknown;
  users: { id: string; username: string }[];
  onChange: (v: unknown) => void;
  compact?: boolean;
}) {
  const base = cn(
    "flex w-full rounded-md border border-line-strong bg-surface-raised px-3 text-sm text-content outline-none focus:border-accent",
    compact ? "h-9" : "h-10",
  );

  switch (col.type) {
    case "long_text":
      // inline (compact) rejimda bir qatorli — to'liq tahrir qator oynasida
      return compact ? (
        <input
          type="text"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        />
      ) : (
        <textarea
          rows={3}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={cn(base, "h-auto py-2")}
        />
      );
    case "number":
      return (
        <input
          type="number"
          value={(value as string) ?? ""}
          min={col.config.min}
          max={col.config.max}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
          className={base}
        />
      );
    case "boolean":
      return (
        <label
          className={cn(
            "flex items-center gap-2 text-sm text-content-muted",
            compact ? "h-9 justify-center" : "h-10",
          )}
        >
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            className="h-4 w-4 rounded border-line-strong accent-[hsl(var(--accent))]"
          />
          {!compact && (value ? "Ha" : "Yo'q")}
        </label>
      );
    case "date":
      return (
        <input
          type="date"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        />
      );
    case "datetime":
      return (
        <input
          type="datetime-local"
          value={value ? isoToLocalInput(String(value)) : ""}
          onChange={(e) =>
            onChange(e.target.value ? new Date(e.target.value).toISOString() : "")
          }
          className={base}
        />
      );
    case "select":
      return (
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        >
          <option value="">—</option>
          {col.config.options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
    case "multi_select": {
      const arr = Array.isArray(value) ? (value as string[]) : [];
      return (
        <div
          className={cn(
            "flex gap-1.5 rounded-md border border-line-strong bg-surface-raised p-2",
            compact ? "h-9 flex-nowrap items-center overflow-x-auto" : "flex-wrap",
          )}
        >
          {col.config.options?.map((o) => {
            const on = arr.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                onClick={() =>
                  onChange(on ? arr.filter((v) => v !== o.value) : [...arr, o.value])
                }
                className={cn(
                  "shrink-0 rounded-full border px-2 py-0.5 text-2xs font-medium",
                  on
                    ? "border-accent bg-accent-soft text-content"
                    : "border-line-strong text-content-muted",
                )}
              >
                {o.label}
              </button>
            );
          })}
        </div>
      );
    }
    case "user":
      return (
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        >
          <option value="">—</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </select>
      );
    default:
      return (
        <input
          type="text"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={base}
        />
      );
  }
}

// ---------- Ko'rsatish ----------

export function CellDisplay({
  col,
  value,
  usernameById,
}: {
  col: DynamicColumn;
  value: unknown;
  usernameById: Map<string, string>;
}) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-content-faint">—</span>;
  }

  if (col.type === "boolean") {
    return (
      <span
        className={cn(
          "inline-flex h-4 w-4 items-center justify-center rounded border",
          value
            ? "border-success bg-success/20 text-success"
            : "border-line-strong text-transparent",
        )}
      >
        {value ? <Check className="h-3 w-3" /> : null}
      </span>
    );
  }

  if (col.type === "select") {
    const opt = col.config.options?.find((o) => o.value === value);
    return <Chip label={opt?.label ?? String(value)} color={opt?.color} />;
  }

  if (col.type === "multi_select") {
    const arr = Array.isArray(value) ? (value as string[]) : [];
    return (
      <span className="flex flex-wrap gap-1">
        {arr.map((v) => {
          const opt = col.config.options?.find((o) => o.value === v);
          return <Chip key={v} label={opt?.label ?? v} color={opt?.color} />;
        })}
      </span>
    );
  }

  if (col.type === "user") {
    const name = usernameById.get(String(value));
    return name ? (
      <Chip label={name} />
    ) : (
      <span className="text-content-faint">(noma'lum)</span>
    );
  }

  if (col.type === "datetime") {
    return <span className="tabular-nums">{formatDateTime(String(value))}</span>;
  }

  if (col.type === "number") {
    return <span className="tabular-nums">{String(value)}</span>;
  }

  return <span className="whitespace-pre-wrap break-words">{cellText(col, value)}</span>;
}

function Chip({ label, color }: { label: string; color?: string }) {
  return (
    <span
      className="inline-flex max-w-[220px] items-center gap-1.5 truncate rounded-full border px-2 py-0.5 text-2xs font-medium"
      style={
        color
          ? { borderColor: `${color}55`, background: `${color}1f`, color }
          : undefined
      }
    >
      {color && (
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ background: color }}
        />
      )}
      <span className="truncate">{label}</span>
    </span>
  );
}

// ---------- Tahrirlash ----------

interface EditorProps {
  col: DynamicColumn;
  value: unknown;
  onCommit: (v: unknown, mode?: "enter" | "blur") => void;
  onCancel: () => void;
  users: { id: string; username: string }[];
}

// Katakning tahrirlagich popoverlari jadval ichida "absolute" bilan joylashtirilsa,
// pastdagi qatorning tabiiy elementlari (masalan native <select>) ustiga chiqib
// ketishi mumkin (jadval stacking context'i tufayli z-index yetarli bo'lmaydi).
// Shu sabab portal orqali document.body'ga chiqarib, "fixed" bilan joylashtiramiz —
// DropdownContent (components/ui/dropdown.tsx) qanday Radix Portal ishlatgan bo'lsa, shunga o'xshash.
function FloatingBox({
  anchorRef,
  onOutsideClick,
  className,
  children,
}: {
  anchorRef: RefObject<HTMLElement>;
  onOutsideClick?: () => void;
  className?: string;
  children: ReactNode;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);

  const reposition = useCallback(() => {
    const anchor = anchorRef.current;
    const box = boxRef.current;
    if (!anchor || !box) return;
    const r = anchor.getBoundingClientRect();
    const bw = box.offsetWidth;
    const bh = box.offsetHeight;
    let top = r.bottom + 4;
    if (top + bh > window.innerHeight - 8) top = Math.max(8, r.top - bh - 4);
    const left = Math.min(Math.max(8, r.left), window.innerWidth - bw - 8);
    setCoords({ top, left });
  }, [anchorRef]);

  useLayoutEffect(() => {
    reposition();
  }, [reposition]);

  useEffect(() => {
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  }, [reposition]);

  useEffect(() => {
    if (!onOutsideClick) return;
    const close = onOutsideClick;
    function handler(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) close();
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onOutsideClick]);

  return createPortal(
    <div
      ref={boxRef}
      style={{ position: "fixed", top: coords?.top ?? -9999, left: coords?.left ?? -9999 }}
      className={className}
    >
      {children}
    </div>,
    document.body,
  );
}

function Popover({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose: () => void;
}) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  return (
    <>
      <span ref={anchorRef} className="pointer-events-none absolute inset-0" aria-hidden />
      <FloatingBox
        anchorRef={anchorRef}
        onOutsideClick={onClose}
        className="z-50 min-w-[200px] max-w-[320px] rounded-md border border-line-strong bg-surface-overlay p-1 shadow-overlay"
      >
        {children}
      </FloatingBox>
    </>
  );
}

export function CellErrorTooltip({ message }: { message: string }) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  return (
    <>
      <span ref={anchorRef} className="pointer-events-none absolute inset-0" aria-hidden />
      <FloatingBox
        anchorRef={anchorRef}
        className="z-50 rounded bg-danger px-1.5 py-0.5 text-2xs text-white shadow"
      >
        {message}
      </FloatingBox>
    </>
  );
}

export function CellEditor(props: EditorProps) {
  const { col } = props;
  switch (col.type) {
    case "long_text":
      return <LongTextEditor {...props} />;
    case "select":
      return <SelectEditor {...props} />;
    case "multi_select":
      return <MultiSelectEditor {...props} />;
    case "user":
      return <UserEditor {...props} />;
    case "date":
      return <InlineInput {...props} inputType="date" />;
    case "datetime":
      return <DateTimeEditor {...props} />;
    case "number":
      return <InlineInput {...props} inputType="number" />;
    default:
      return <InlineInput {...props} inputType="text" />;
  }
}

function InlineInput({
  value,
  onCommit,
  onCancel,
  inputType,
  col,
}: EditorProps & { inputType: string }) {
  const [v, setV] = useState(value == null ? "" : String(value));
  const done = useRef(false);
  const finish = (mode: "enter" | "blur") => {
    if (done.current) return;
    done.current = true;
    onCommit(v === "" ? null : v, mode);
  };
  return (
    <input
      autoFocus
      type={inputType}
      value={v}
      min={col.type === "number" ? col.config.min : undefined}
      max={col.type === "number" ? col.config.max : undefined}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => finish("blur")}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          finish("enter");
        }
        if (e.key === "Escape") {
          e.preventDefault();
          done.current = true;
          onCancel();
        }
      }}
      className="h-full w-full rounded-sm border border-accent bg-surface-raised px-2 text-sm text-content outline-none ring-2 ring-accent/20"
    />
  );
}

function DateTimeEditor({ value, onCommit, onCancel }: EditorProps) {
  // ISO(UTC) -> datetime-local (mahalliy) va orqaga
  const [v, setV] = useState(value ? isoToLocalInput(String(value)) : "");
  const done = useRef(false);
  const finish = (mode: "enter" | "blur") => {
    if (done.current) return;
    done.current = true;
    onCommit(v === "" ? null : new Date(v).toISOString(), mode);
  };
  return (
    <input
      autoFocus
      type="datetime-local"
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => finish("blur")}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          finish("enter");
        }
        if (e.key === "Escape") {
          e.preventDefault();
          done.current = true;
          onCancel();
        }
      }}
      className="h-full w-full rounded-sm border border-accent bg-surface-raised px-2 text-sm text-content outline-none ring-2 ring-accent/20"
    />
  );
}

function LongTextEditor({ value, onCommit, onCancel }: EditorProps) {
  const [v, setV] = useState(value == null ? "" : String(value));
  return (
    <Popover onClose={onCancel}>
      <textarea
        autoFocus
        rows={5}
        value={v}
        onChange={(e) => setV(e.target.value)}
        className="w-72 resize-y rounded-sm border border-line-strong bg-surface-raised p-2 text-sm text-content outline-none focus:border-accent"
      />
      <div className="mt-1 flex justify-end gap-1">
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Bekor
        </Button>
        <Button size="sm" onClick={() => onCommit(v === "" ? null : v)}>
          Saqlash
        </Button>
      </div>
    </Popover>
  );
}

function SelectEditor({ col, value, onCommit, onCancel }: EditorProps) {
  return (
    <Popover onClose={onCancel}>
      <ul className="max-h-64 overflow-auto">
        <li>
          <button
            className="w-full rounded-sm px-2 py-1.5 text-left text-xs text-content-faint hover:bg-surface-raised"
            onClick={() => onCommit(null)}
          >
            — tozalash —
          </button>
        </li>
        {col.config.options?.map((o) => (
          <li key={o.value}>
            <button
              className="flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm hover:bg-surface-raised"
              onClick={() => onCommit(o.value)}
            >
              <Chip label={o.label} color={o.color} />
              {value === o.value && <Check className="h-3.5 w-3.5 text-accent" />}
            </button>
          </li>
        ))}
      </ul>
    </Popover>
  );
}

function MultiSelectEditor({ col, value, onCommit, onCancel }: EditorProps) {
  const [sel, setSel] = useState<string[]>(Array.isArray(value) ? [...(value as string[])] : []);
  const toggle = (v: string) =>
    setSel((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));
  return (
    <Popover onClose={() => onCommit(sel)}>
      <ul className="max-h-64 overflow-auto">
        {col.config.options?.map((o) => (
          <li key={o.value}>
            <button
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-surface-raised"
              onClick={() => toggle(o.value)}
            >
              <span
                className={cn(
                  "flex h-3.5 w-3.5 items-center justify-center rounded border",
                  sel.includes(o.value)
                    ? "border-accent bg-accent text-accent-fg"
                    : "border-line-strong",
                )}
              >
                {sel.includes(o.value) && <Check className="h-2.5 w-2.5" />}
              </span>
              <Chip label={o.label} color={o.color} />
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-1 flex justify-end gap-1 border-t border-line pt-1">
        <Button size="sm" variant="ghost" onClick={onCancel}>
          <X className="h-3.5 w-3.5" />
        </Button>
        <Button size="sm" onClick={() => onCommit(sel)}>
          Tayyor
        </Button>
      </div>
    </Popover>
  );
}

function UserEditor({ value, onCommit, onCancel, users }: EditorProps) {
  const [q, setQ] = useState("");
  const filtered = users
    .filter((u) => u.username.toLowerCase().includes(q.toLowerCase()))
    .slice(0, 50);
  return (
    <Popover onClose={onCancel}>
      <input
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Qidirish…"
        className="mb-1 w-full rounded-sm border border-line-strong bg-surface-raised px-2 py-1 text-sm outline-none focus:border-accent"
      />
      <ul className="max-h-56 overflow-auto">
        <li>
          <button
            className="w-full rounded-sm px-2 py-1.5 text-left text-xs text-content-faint hover:bg-surface-raised"
            onClick={() => onCommit(null)}
          >
            — tozalash —
          </button>
        </li>
        {filtered.map((u) => (
          <li key={u.id}>
            <button
              className="flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm hover:bg-surface-raised"
              onClick={() => onCommit(u.id)}
            >
              {u.username}
              {value === u.id && <Check className="h-3.5 w-3.5 text-accent" />}
            </button>
          </li>
        ))}
      </ul>
    </Popover>
  );
}
