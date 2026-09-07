import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  ChevronRight,
  ListTodo,
  Plus,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { writableSectionsFor } from "@/lib/types";
import type {
  SectionSummary,
  SectionTodo,
  TableSection,
  TodoScope,
} from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

interface Props {
  section: "soc" | "dlp";
  title: string;
  description: string;
  icon: LucideIcon;
}

const todayStr = () => new Date().toISOString().slice(0, 10);

export function SectionPanel({ section, title, description, icon: Icon }: Props) {
  const { user } = useAuth();
  const canWriteShared = !!user && writableSectionsFor(user.role).includes(section as TableSection);

  return (
    <PageTransition>
      <PageHeader
        title={title}
        description={description}
        actions={<Badge variant="accent">{section.toUpperCase()}</Badge>}
      />
      <div className="space-y-6">
        <TodoBlock section={section} canWriteShared={canWriteShared} icon={Icon} />
        <SummaryBlock section={section} />
      </div>
    </PageTransition>
  );
}

// --- Topshiriqlar -----------------------------------------------------------

function TodoBlock({
  section,
  canWriteShared,
  icon: Icon,
}: {
  section: "soc" | "dlp";
  canWriteShared: boolean;
  icon: LucideIcon;
}) {
  const [scope, setScope] = useState<TodoScope>("personal");
  const [items, setItems] = useState<SectionTodo[] | null>(null);
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setItems(null);
    try {
      const { data } = await api.get<SectionTodo[]>(`/sections/${section}/todos`, {
        params: { scope },
      });
      setItems(data);
    } catch (e) {
      toast.error(apiError(e));
      setItems([]);
    }
  }, [section, scope]);

  useEffect(() => {
    void load();
  }, [load]);

  const canAdd = scope === "personal" || canWriteShared;

  async function add() {
    const t = text.trim();
    if (!t || adding) return;
    setAdding(true);
    try {
      const { data } = await api.post<SectionTodo>(`/sections/${section}/todos`, {
        scope,
        text: t,
        due_date: due || null,
      });
      setItems((xs) => [...(xs ?? []).filter((x) => !x.is_done), data, ...(xs ?? []).filter((x) => x.is_done)]);
      setText("");
      setDue("");
    } catch (e) {
      toast.error(apiError(e, "Qo'shib bo'lmadi"));
    } finally {
      setAdding(false);
    }
  }

  async function toggle(item: SectionTodo) {
    const next = !item.is_done;
    setItems((xs) =>
      (xs ?? [])
        .map((x) => (x.id === item.id ? { ...x, is_done: next } : x))
        .sort((a, b) => Number(a.is_done) - Number(b.is_done)),
    );
    try {
      await api.patch(`/sections/${section}/todos/${item.id}`, { is_done: next });
    } catch (e) {
      toast.error(apiError(e));
      void load();
    }
  }

  async function remove(item: SectionTodo) {
    setItems((xs) => (xs ?? []).filter((x) => x.id !== item.id));
    try {
      await api.delete(`/sections/${section}/todos/${item.id}`);
    } catch (e) {
      toast.error(apiError(e));
      void load();
    }
  }

  const openCount = (items ?? []).filter((x) => !x.is_done).length;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-sm font-medium text-content">
            <ListTodo className="h-4 w-4 text-accent" />
            Topshiriqlar
            {items && (
              <span className="text-2xs font-normal text-content-faint">
                {openCount} ochiq
              </span>
            )}
          </div>
          <div className="ml-auto flex items-center gap-1 rounded-md border border-line-strong p-0.5">
            {(["personal", "shared"] as TodoScope[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScope(s)}
                className={cn(
                  "rounded px-2 py-1 text-2xs font-medium transition-colors",
                  scope === s
                    ? "bg-accent-soft text-content"
                    : "text-content-muted hover:text-content",
                )}
              >
                {s === "personal" ? "Mening" : "Bo'lim"}
              </button>
            ))}
          </div>
        </div>

        {canAdd && (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              placeholder={
                scope === "personal" ? "Nima qilmoqchisiz?" : "Bo'lim uchun topshiriq"
              }
              className="h-9 min-w-[200px] flex-1"
            />
            <input
              type="date"
              value={due}
              min={todayStr()}
              onChange={(e) => setDue(e.target.value)}
              title="Muddat (ixtiyoriy)"
              className="h-9 rounded-md border border-line-strong bg-surface-raised px-2 text-xs text-content outline-none focus:border-accent"
            />
            <Button size="sm" className="h-9" onClick={add} loading={adding} disabled={!text.trim()}>
              <Plus className="h-4 w-4" />
              Qo'shish
            </Button>
          </div>
        )}
        {!canAdd && scope === "shared" && (
          <p className="text-2xs text-content-faint">
            Bo'lim topshiriqlarini faqat ko'rish mumkin (yozish ruxsati yo'q).
          </p>
        )}

        {!items ? (
          <div className="flex justify-center py-6">
            <Spinner className="h-4 w-4" />
          </div>
        ) : items.length === 0 ? (
          <p className="py-4 text-center text-xs text-content-faint">
            <Icon className="mx-auto mb-1 h-4 w-4" />
            Hozircha topshiriq yo'q
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {items.map((it) => (
              <TodoRow key={it.id} item={it} onToggle={toggle} onRemove={remove} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function TodoRow({
  item,
  onToggle,
  onRemove,
}: {
  item: SectionTodo;
  onToggle: (i: SectionTodo) => void;
  onRemove: (i: SectionTodo) => void;
}) {
  const overdue =
    !item.is_done && item.due_date != null && item.due_date < todayStr();
  return (
    <li className="group flex items-center gap-2.5 py-2 text-sm">
      <button
        type="button"
        onClick={() => onToggle(item)}
        aria-pressed={item.is_done}
        className={cn(
          "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
          item.is_done
            ? "border-success bg-success/20 text-success"
            : "border-line-strong text-transparent hover:border-content-faint",
        )}
      >
        <Check className="h-3 w-3" />
      </button>
      <span
        className={cn(
          "min-w-0 flex-1 truncate",
          item.is_done && "text-content-faint line-through",
        )}
        title={item.text}
      >
        {item.text}
      </span>
      {item.due_date && (
        <span
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 text-2xs tabular-nums",
            overdue
              ? "bg-danger/15 text-danger"
              : "bg-surface-overlay text-content-faint",
          )}
        >
          {item.due_date}
        </span>
      )}
      <span className="hidden shrink-0 text-2xs text-content-faint sm:inline">
        {item.owner_name ?? "—"} · {relativeTime(item.created_at)}
      </span>
      <button
        type="button"
        onClick={() => onRemove(item)}
        className="shrink-0 rounded p-1 text-content-faint opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
        aria-label="O'chirish"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </li>
  );
}

// --- Statistika -----------------------------------------------------------

function SummaryBlock({ section }: { section: "soc" | "dlp" }) {
  const [data, setData] = useState<SectionSummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setData(null);
    setFailed(false);
    api
      .get<SectionSummary>(`/sections/${section}/summary`)
      .then((r) => setData(r.data))
      .catch(() => setFailed(true));
  }, [section]);

  if (failed) {
    return (
      <Card>
        <CardContent className="py-4 text-center text-xs text-content-faint">
          Statistikani yuklab bo'lmadi.
        </CardContent>
      </Card>
    );
  }
  if (!data) {
    return (
      <Card>
        <CardContent className="flex justify-center py-8">
          <Spinner className="h-4 w-4" />
        </CardContent>
      </Card>
    );
  }

  const t = data.totals;
  const tiles: { label: string; value: number | string }[] = [
    { label: "Jadval", value: t.tables },
    { label: "Qator", value: t.rows },
    { label: "Bajarilgan", value: t.done },
    { label: "Ochiq", value: t.open },
    { label: "7 kunda +", value: t.added_7d },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map((x) => (
          <Card key={x.label}>
            <CardContent className="py-3">
              <p className="text-2xs text-content-faint">{x.label}</p>
              <p className="text-lg font-semibold tabular-nums text-content">{x.value}</p>
            </CardContent>
          </Card>
        ))}
        <Card>
          <CardContent className="py-3">
            <p className="text-2xs text-content-faint">14 kunlik trend</p>
            <Sparkline points={data.trend.map((p) => p.count)} />
          </CardContent>
        </Card>
      </div>

      {data.tables.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {data.tables.map((tbl) => {
            const pct = tbl.row_count > 0 ? (tbl.done_count / tbl.row_count) * 100 : 0;
            return (
              <Card key={tbl.id}>
                <CardContent className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Link
                      to={`/tables/${tbl.id}`}
                      className="truncate font-medium text-content hover:text-accent"
                    >
                      {tbl.name}
                    </Link>
                    <span className="shrink-0 text-2xs text-content-faint">
                      {relativeTime(tbl.updated_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-2xs text-content-faint">
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-overlay">
                      <span
                        className="block h-full rounded-full bg-success"
                        style={{ width: `${Math.min(100, Math.round(pct))}%` }}
                      />
                    </span>
                    <span className="tabular-nums">
                      {tbl.done_count}/{tbl.row_count}
                    </span>
                  </div>
                  {tbl.breakdown.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {tbl.breakdown_label && (
                        <span className="text-2xs text-content-faint">
                          {tbl.breakdown_label}:
                        </span>
                      )}
                      {tbl.breakdown.slice(0, 6).map((e) => (
                        <span
                          key={e.value}
                          className="inline-flex items-center gap-1 rounded-full border border-line-strong px-1.5 py-0.5 text-2xs"
                        >
                          {e.color && (
                            <span
                              className="h-1.5 w-1.5 rounded-full"
                              style={{ background: e.color }}
                            />
                          )}
                          <span className="text-content-muted">{e.label}</span>
                          <span className="font-medium tabular-nums text-content">
                            {e.count}
                          </span>
                        </span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {data.recent.length > 0 && (
        <Card>
          <CardContent className="space-y-1.5">
            <p className="text-2xs font-medium text-content-faint">So'nggi o'zgarishlar</p>
            <ul className="space-y-1">
              {data.recent.map((r, i) => (
                <li
                  key={`${r.row_id}-${i}`}
                  className="flex items-center gap-2 text-xs text-content-muted"
                >
                  <ChevronRight className="h-3 w-3 shrink-0 text-content-faint" />
                  <Link to={`/tables/${r.table_id}`} className="shrink-0 font-medium hover:text-accent">
                    {r.table_name}
                  </Link>
                  <span className="shrink-0 text-content-faint">{ACTION_UZ[r.action] ?? r.action}</span>
                  <span className="truncate text-content-faint">
                    · {r.changed_by_name ?? "—"}
                  </span>
                  <span className="ml-auto shrink-0 text-2xs text-content-faint">
                    {relativeTime(r.changed_at)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const ACTION_UZ: Record<string, string> = {
  create: "qo'shildi",
  update: "o'zgardi",
  delete: "o'chirildi",
};

function Sparkline({ points }: { points: number[] }) {
  if (points.length === 0) return <p className="text-sm text-content-faint">—</p>;
  const max = Math.max(1, ...points);
  const w = 120;
  const h = 28;
  const step = points.length > 1 ? w / (points.length - 1) : w;
  const d = points
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i * step).toFixed(1)} ${(h - (v / max) * h).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="mt-1 overflow-visible">
      <path d={d} fill="none" stroke="hsl(var(--accent))" strokeWidth="1.5" />
    </svg>
  );
}
