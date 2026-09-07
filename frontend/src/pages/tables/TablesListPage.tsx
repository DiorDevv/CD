import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Archive,
  ArchiveRestore,
  Columns3,
  Database,
  MoreVertical,
  Plus,
  Rows3,
  Search,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  SECTION_LABELS,
  writableSectionsFor,
  type DynamicTable,
  type TablePage,
  type TableSection,
} from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  Dropdown,
  DropdownContent,
  DropdownItem,
  DropdownSeparator,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { NewTableDialog } from "@/pages/tables/NewTableDialog";

type SortKey = "name" | "updated" | "rows";
type SectionFilter = "all" | TableSection;

const SORT_LABELS: Record<SortKey, string> = {
  name: "Nom",
  updated: "Oxirgi o'zgarish",
  rows: "Qator soni",
};

export function TablesListPage() {
  const { user } = useAuth();
  const canCreate = user ? writableSectionsFor(user.role).length > 0 : false;
  const [tables, setTables] = useState<DynamicTable[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const [query, setQuery] = useState("");
  const [sectionFilter, setSectionFilter] = useState<SectionFilter>("all");
  const [sortBy, setSortBy] = useState<SortKey>("name");
  const [pendingDelete, setPendingDelete] = useState<DynamicTable | null>(null);

  const isSuper = user?.role === "super_admin";
  const canManage = useCallback(
    (t: DynamicTable) =>
      !!user && writableSectionsFor(user.role).includes(t.section),
    [user],
  );

  async function toggleArchive(t: DynamicTable) {
    try {
      await api.patch(`/tables/${t.id}`, { is_archived: !t.is_archived });
      toast.success(t.is_archived ? "Arxivdan chiqarildi" : "Arxivga o'tkazildi");
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function deleteTable(t: DynamicTable) {
    try {
      await api.delete(`/tables/${t.id}`);
      toast.success(`"${t.name}" o'chirildi`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<TablePage>("/tables", {
        params: { include_archived: showArchived, limit: 200 },
      });
      setTables(data.items);
    } catch (e) {
      setError(apiError(e));
    }
  }, [showArchived]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    let items = tables ?? [];
    const q = query.trim().toLowerCase();
    if (q) items = items.filter((t) => t.name.toLowerCase().includes(q));
    if (sectionFilter !== "all") items = items.filter((t) => t.section === sectionFilter);
    const sorted = [...items].sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "rows") return b.row_count - a.row_count;
      return b.updated_at.localeCompare(a.updated_at);
    });
    return sorted;
  }, [tables, query, sectionFilter, sortBy]);

  const totals = useMemo(
    () => ({
      tables: filtered.length,
      rows: filtered.reduce((s, t) => s + t.row_count, 0),
      done: filtered.reduce((s, t) => s + t.done_count, 0),
    }),
    [filtered],
  );

  const grouped = groupBySection(filtered);
  const sectionsPresent = useMemo(
    () => Array.from(new Set((tables ?? []).map((t) => t.section))),
    [tables],
  );

  return (
    <PageTransition>
      <PageHeader
        title="Jadvallar"
        description="Bo'limingizga tegishli jadvallarni tuzing va to'ldiring."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowArchived((v) => !v)}
            >
              <Archive className="h-4 w-4" />
              {showArchived ? "Arxivni yashirish" : "Arxivni ko'rsatish"}
            </Button>
            {canCreate && (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Yangi jadval
              </Button>
            )}
          </div>
        }
      />

      {error && (
        <div role="alert" className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}

      {tables && tables.length > 0 && (
        <div className="mb-5 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative w-56">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-content-faint" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Jadval nomi bo'yicha"
                className="h-9 pl-9"
                aria-label="Jadvallarni qidirish"
              />
            </div>

            {sectionsPresent.length > 1 && (
              <div className="flex items-center gap-1 rounded-md border border-line-strong p-0.5">
                {(["all", ...sectionsPresent] as SectionFilter[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSectionFilter(s)}
                    className={cn(
                      "rounded px-2 py-1 text-2xs font-medium transition-colors",
                      sectionFilter === s
                        ? "bg-accent-soft text-content"
                        : "text-content-muted hover:text-content",
                    )}
                  >
                    {s === "all" ? "Hammasi" : SECTION_LABELS[s]}
                  </button>
                ))}
              </div>
            )}

            <label className="flex items-center gap-1.5 text-2xs text-content-muted">
              Saralash:
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortKey)}
                className="h-9 rounded-md border border-line-strong bg-surface-raised px-2 text-xs text-content outline-none focus:border-accent"
              >
                {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                  <option key={k} value={k}>
                    {SORT_LABELS[k]}
                  </option>
                ))}
              </select>
            </label>

            <span className="ml-auto text-2xs text-content-faint">
              {totals.tables} jadval · {totals.rows} qator
              {totals.done > 0 && ` · ${totals.done} bajarilgan`}
            </span>
          </div>
        </div>
      )}

      {!tables && (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}

      {tables && tables.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-14 text-center">
            <Database className="h-6 w-6 text-content-faint" />
            <p className="text-sm text-content-muted">Hali jadval yo'q</p>
            {canCreate && (
              <Button className="mt-2" size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" />
                Birinchi jadvalni yaratish
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {tables && tables.length > 0 && filtered.length === 0 && (
        <p className="py-10 text-center text-sm text-content-muted">
          Filtrga mos jadval topilmadi.
        </p>
      )}

      {tables &&
        grouped.map(([section, items]) => (
          <div key={section} className="mb-6">
            <div className="mb-2 flex items-center gap-2">
              <Badge variant={section === "shared" ? "neutral" : "accent"}>
                {SECTION_LABELS[section]}
              </Badge>
              <span className="text-2xs text-content-faint">{items.length} ta</span>
            </div>
            <div className="grid grid-cols-3 gap-4">
              {items.map((t, i) => {
                const manageable = canManage(t) || isSuper;
                return (
                <motion.div
                  key={t.id}
                  className="group relative"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.25), duration: 0.2 }}
                >
                  {manageable && (
                    <div className="absolute right-1.5 top-1.5 z-10">
                      <Dropdown>
                        <DropdownTrigger asChild>
                          <button
                            type="button"
                            onClick={(e) => e.stopPropagation()}
                            aria-label={`${t.name} amallari`}
                            className="rounded p-1 text-content-faint opacity-0 transition-opacity hover:bg-surface-overlay hover:text-content focus:opacity-100 group-hover:opacity-100"
                          >
                            <MoreVertical className="h-4 w-4" />
                          </button>
                        </DropdownTrigger>
                        <DropdownContent align="end">
                          {canManage(t) && (
                            <DropdownItem onSelect={() => toggleArchive(t)}>
                              {t.is_archived ? (
                                <>
                                  <ArchiveRestore className="h-3.5 w-3.5" />
                                  Arxivdan chiqarish
                                </>
                              ) : (
                                <>
                                  <Archive className="h-3.5 w-3.5" />
                                  Arxivga o'tkazish
                                </>
                              )}
                            </DropdownItem>
                          )}
                          {isSuper && (
                            <>
                              {canManage(t) && <DropdownSeparator />}
                              <DropdownItem destructive onSelect={() => setPendingDelete(t)}>
                                <Trash2 className="h-3.5 w-3.5" />
                                O'chirish
                              </DropdownItem>
                            </>
                          )}
                        </DropdownContent>
                      </Dropdown>
                    </div>
                  )}
                  <Link to={`/tables/${t.id}`}>
                    <Card className="h-full transition-colors hover:border-line-strong hover:bg-surface-raised">
                      <CardContent className="space-y-3">
                        <div className="flex items-start justify-between gap-2 pr-6">
                          <p className="font-medium text-content">{t.name}</p>
                          {t.is_archived && (
                            <Badge variant="warning">
                              <Archive className="h-3 w-3" />
                              Arxiv
                            </Badge>
                          )}
                        </div>
                        {t.description && (
                          <p className="line-clamp-2 text-xs text-content-muted">
                            {t.description}
                          </p>
                        )}
                        <div className="flex items-center gap-4 text-2xs text-content-faint">
                          <span className="flex items-center gap-1">
                            <Columns3 className="h-3 w-3" />
                            {t.column_count} ustun
                          </span>
                          <span className="flex items-center gap-1">
                            <Rows3 className="h-3 w-3" />
                            {t.row_count} qator
                          </span>
                          <span className="ml-auto">{relativeTime(t.updated_at)}</span>
                        </div>

                        {t.done_count > 0 && t.row_count > 0 && (
                          <div className="flex items-center gap-2">
                            <span className="h-1 flex-1 overflow-hidden rounded-full bg-surface-overlay">
                              <span
                                className="block h-full rounded-full bg-success"
                                style={{
                                  width: `${Math.min(100, Math.round((t.done_count / t.row_count) * 100))}%`,
                                }}
                              />
                            </span>
                            <span className="text-2xs tabular-nums text-content-faint">
                              {t.done_count}/{t.row_count}
                            </span>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </Link>
                </motion.div>
                );
              })}
            </div>
          </div>
        ))}

      <NewTableDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(v) => !v && setPendingDelete(null)}
        title={`"${pendingDelete?.name}" jadvalini butunlay o'chirish`}
        description="Jadval, barcha ustunlar, qatorlar va tarix butunlay o'chiriladi. Ortga qaytarib bo'lmaydi. (Arxivga o'tkazishni ko'rib chiqing.)"
        confirmLabel="Butunlay o'chirish"
        variant="danger"
        onConfirm={async () => {
          if (pendingDelete) await deleteTable(pendingDelete);
        }}
      />
    </PageTransition>
  );
}

function groupBySection(tables: DynamicTable[]): [DynamicTable["section"], DynamicTable[]][] {
  const order: DynamicTable["section"][] = ["soc", "dlp", "shared"];
  const map = new Map<DynamicTable["section"], DynamicTable[]>();
  for (const t of tables) {
    const arr = map.get(t.section) ?? [];
    arr.push(t);
    map.set(t.section, arr);
  }
  return order.filter((s) => map.has(s)).map((s) => [s, map.get(s)!]);
}
