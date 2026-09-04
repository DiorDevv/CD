import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Copy,
  Download,
  History,
  MoveLeft,
  MoveRight,
  Pencil,
  Plus,
  Search,
  Settings2,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError, apiStatus, fieldErrors } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useDirectory } from "@/lib/directory";
import { defaultCellValue, typeMeta } from "@/lib/dynamic";
import { writableSectionsFor, SECTION_LABELS } from "@/lib/types";
import type { DynamicColumn, DynamicRow, DynamicTableDetail, RowPage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PageTransition } from "@/components/PageTransition";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  Dropdown,
  DropdownContent,
  DropdownItem,
  DropdownSeparator,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { CellDisplay, CellEditor, CellErrorTooltip, RowFieldInput } from "@/pages/tables/cells";
import { ColumnDialog } from "@/pages/tables/ColumnDialog";
import { NewRowDialog } from "@/pages/tables/NewRowDialog";
import { ImportDialog } from "@/pages/tables/ImportDialog";
import { ExportDialog } from "@/pages/tables/ExportDialog";
import { RowHistoryDialog } from "@/pages/tables/RowHistoryDialog";

const PAGE_SIZE = 50;

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex min-w-[1.4em] items-center justify-center rounded border border-line-strong bg-surface-raised px-1 py-px font-sans text-[0.65rem] leading-none text-content-muted">
      {children}
    </kbd>
  );
}

export function TableGridPage() {
  const { tableId = "" } = useParams();
  const { user } = useAuth();
  const { users, byId } = useDirectory();
  const usernameById = useMemo(
    () => new Map([...byId].map(([id, u]) => [id, u.username])),
    [byId],
  );

  const [table, setTable] = useState<DynamicTableDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [rows, setRows] = useState<DynamicRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [rowsLoading, setRowsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<{ rowId: string; key: string } | null>(null);
  const [active, setActive] = useState<{ r: number; c: number } | null>(null);
  const [savingCell, setSavingCell] = useState<string | null>(null); // `${rowId}:${key}`
  const [cellError, setCellError] = useState<{ rowId: string; key: string; msg: string } | null>(null);

  const [colDialog, setColDialog] = useState<{ open: boolean; column: DynamicColumn | null }>({
    open: false,
    column: null,
  });
  const [newRowOpen, setNewRowOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [historyRowId, setHistoryRowId] = useState<string | null>(null);
  const [pendingDeleteCol, setPendingDeleteCol] = useState<DynamicColumn | null>(null);
  const [pendingDeleteRow, setPendingDeleteRow] = useState<DynamicRow | null>(null);
  const [pendingDeleteTable, setPendingDeleteTable] = useState(false);

  // Inline "yangi qator" qoralamasi
  const [newRow, setNewRow] = useState<Record<string, unknown>>({});
  const [newRowErrors, setNewRowErrors] = useState<Record<string, string>>({});
  const [newRowSaving, setNewRowSaving] = useState(false);

  const firstRowsLoad = useRef(true);
  const gridRef = useRef<HTMLDivElement>(null);
  const dragCol = useRef<number | null>(null);
  const [dragOverCol, setDragOverCol] = useState<number | null>(null);

  const canWrite =
    !!table &&
    !!user &&
    user.role !== "viewer" &&
    writableSectionsFor(user.role).includes(table.section) &&
    !table.is_archived;
  const isSuper = user?.role === "super_admin";

  const sortedCols = useMemo(
    () => (table ? [...table.columns].sort((a, b) => a.position - b.position) : []),
    [table],
  );

  const seedNewRow = useCallback((cols: DynamicColumn[]) => {
    const seed: Record<string, unknown> = {};
    for (const c of cols) {
      const dv = defaultCellValue(c);
      if (dv !== "" && dv !== false) seed[c.key] = dv;
    }
    setNewRow(seed);
    setNewRowErrors({});
  }, []);

  const loadTable = useCallback(async () => {
    try {
      const { data } = await api.get<DynamicTableDetail>(`/tables/${tableId}`);
      setTable(data);
      seedNewRow([...data.columns].sort((a, b) => a.position - b.position));
    } catch (e) {
      if (apiStatus(e) === 404) setNotFound(true);
      else setError(apiError(e));
    }
  }, [tableId, seedNewRow]);

  const loadRows = useCallback(async () => {
    setRowsLoading(true);
    try {
      const { data } = await api.get<RowPage>(`/tables/${tableId}/rows`, {
        params: {
          limit: PAGE_SIZE,
          offset,
          ...(sort ? { sort } : {}),
          ...(debouncedQ ? { q: debouncedQ } : {}),
        },
      });
      setRows(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setRowsLoading(false);
      firstRowsLoad.current = false;
    }
  }, [tableId, offset, sort, debouncedQ]);

  useEffect(() => {
    void loadTable();
  }, [loadTable]);
  useEffect(() => {
    void loadRows();
  }, [loadRows]);
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQ(q.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  // active katak diapazondan chiqib ketmasin
  useEffect(() => {
    setActive((a) => {
      if (!a) return a;
      if (rows.length === 0 || sortedCols.length === 0) return null;
      return {
        r: Math.min(a.r, rows.length - 1),
        c: Math.min(a.c, sortedCols.length - 1),
      };
    });
  }, [rows.length, sortedCols.length]);

  async function commitCell(
    row: DynamicRow,
    col: DynamicColumn,
    value: unknown,
    mode?: "enter" | "blur",
  ) {
    setEditing(null);
    if (mode === "enter") {
      setActive((a) =>
        a ? { r: Math.min(rows.length - 1, a.r + 1), c: a.c } : a,
      );
      gridRef.current?.focus();
    }
    const cur = row.data[col.key] ?? null;
    if (JSON.stringify(cur) === JSON.stringify(value ?? null)) return;
    const cellKey = `${row.id}:${col.key}`;
    setSavingCell(cellKey);
    setCellError(null);
    try {
      const { data } = await api.patch<DynamicRow>(`/tables/${tableId}/rows/${row.id}`, {
        data: { [col.key]: value },
        expected_updated_at: row.updated_at,
      });
      setRows((rs) => rs.map((r) => (r.id === row.id ? data : r)));
    } catch (e) {
      const status = apiStatus(e);
      const fe = fieldErrors(e);
      if (status === 409) {
        toast.error("Bu qatorni boshqa birov o'zgartirdi — yangilanmoqda");
        await loadRows();
      } else if (fe && fe[col.key]) {
        setCellError({ rowId: row.id, key: col.key, msg: fe[col.key] });
      } else {
        toast.error(apiError(e, "Katakni saqlab bo'lmadi"));
      }
    } finally {
      setSavingCell(null);
    }
  }

  function onGridKeyDown(e: React.KeyboardEvent) {
    // forma elementidan kelgan hodisalarni (inline qator, tahrirlagich) o'tkazib yuboramiz
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (editing || !active || sortedCols.length === 0 || rows.length === 0) return;
    const maxR = rows.length - 1;
    const maxC = sortedCols.length - 1;
    let { r, c } = active;
    switch (e.key) {
      case "ArrowUp":
        r = Math.max(0, r - 1);
        break;
      case "ArrowDown":
        r = Math.min(maxR, r + 1);
        break;
      case "ArrowLeft":
        c = Math.max(0, c - 1);
        break;
      case "ArrowRight":
        c = Math.min(maxC, c + 1);
        break;
      case "Tab":
        e.preventDefault();
        c += e.shiftKey ? -1 : 1;
        if (c > maxC) {
          c = 0;
          r = Math.min(maxR, r + 1);
        } else if (c < 0) {
          c = maxC;
          r = Math.max(0, r - 1);
        }
        break;
      case "Enter":
      case "F2": {
        if (!canWrite) return;
        e.preventDefault();
        const col = sortedCols[c];
        const row = rows[r];
        if (col.type === "boolean") {
          void commitCell(row, col, !row.data[col.key]);
        } else {
          setEditing({ rowId: row.id, key: col.key });
        }
        return;
      }
      case "Escape":
        setActive(null);
        return;
      case "Backspace":
      case "Delete": {
        if (!canWrite) return;
        e.preventDefault();
        const col = sortedCols[c];
        const row = rows[r];
        if (col.type !== "boolean") void commitCell(row, col, null);
        return;
      }
      default:
        return;
    }
    e.preventDefault();
    setActive({ r, c });
  }

  function cycleSort(key: string) {
    setOffset(0);
    setSort((s) => {
      if (s === `${key}:asc`) return `${key}:desc`;
      if (s === `${key}:desc`) return null;
      return `${key}:asc`;
    });
  }

  async function reorderColumns(from: number, to: number) {
    if (from === to || to < 0 || to >= sortedCols.length) return;
    const next = [...sortedCols];
    const [m] = next.splice(from, 1);
    next.splice(to, 0, m);
    try {
      await api.post(`/tables/${tableId}/columns/reorder`, {
        items: next.map((c, i) => ({ id: c.id, position: i })),
      });
      await loadTable();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function deleteColumn(col: DynamicColumn) {
    try {
      await api.delete(`/tables/${tableId}/columns/${col.id}`);
      toast.success(`"${col.label}" ustuni o'chirildi`);
      await Promise.all([loadTable(), loadRows()]);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function deleteRow(row: DynamicRow) {
    try {
      await api.delete(`/tables/${tableId}/rows/${row.id}`);
      toast.success("Qator o'chirildi");
      if (rows.length === 1 && offset > 0) setOffset(Math.max(0, offset - PAGE_SIZE));
      else await loadRows();
      void loadTable();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function duplicateRow(row: DynamicRow) {
    try {
      await api.post(`/tables/${tableId}/rows`, { data: row.data });
      toast.success("Qator nusxalandi");
      await loadRows();
      void loadTable();
    } catch (e) {
      toast.error(apiError(e, "Nusxalab bo'lmadi"));
    }
  }

  async function commitNewRow() {
    const clean: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(newRow)) {
      if (v === "" || v === undefined || v === null) continue;
      if (Array.isArray(v) && v.length === 0) continue;
      clean[k] = v;
    }
    if (Object.keys(clean).length === 0) return;
    setNewRowSaving(true);
    setNewRowErrors({});
    try {
      await api.post(`/tables/${tableId}/rows`, { data: clean });
      seedNewRow(sortedCols);
      await loadRows();
      void loadTable();
      if (offset + rows.length < total + 1) {
        // yangi qator oxirgi sahifada bo'lsa unga o'tamiz
      }
    } catch (e) {
      const fe = fieldErrors(e);
      if (fe) setNewRowErrors(fe);
      else toast.error(apiError(e, "Qator qo'shib bo'lmadi"));
    } finally {
      setNewRowSaving(false);
    }
  }

  async function toggleArchive() {
    if (!table) return;
    try {
      await api.patch(`/tables/${tableId}`, { is_archived: !table.is_archived });
      toast.success(table.is_archived ? "Arxivdan chiqarildi" : "Arxivga o'tkazildi");
      await loadTable();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function deleteTable() {
    try {
      await api.delete(`/tables/${tableId}`);
      toast.success("Jadval o'chirildi");
      window.location.href = "/tables";
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function renameTable(name: string) {
    if (!table || name.trim() === table.name || !name.trim()) return;
    try {
      const { data } = await api.patch<DynamicTableDetail>(`/tables/${tableId}`, {
        name: name.trim(),
      });
      setTable(data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  // --- render ---

  if (notFound) {
    return (
      <PageTransition>
        <div className="grid place-items-center py-24 text-center">
          <p className="text-sm text-content-muted">Jadval topilmadi yoki ruxsat yo'q.</p>
          <Link to="/tables" className="mt-3 text-xs text-accent hover:underline">
            ← Jadvallar ro'yxatiga qaytish
          </Link>
        </div>
      </PageTransition>
    );
  }

  if (!table) {
    return (
      <PageTransition>
        <div className="flex justify-center py-24">
          <Spinner className="h-5 w-5" />
        </div>
      </PageTransition>
    );
  }

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const showSkeleton = rowsLoading && firstRowsLoad.current;
  const showInlineAdd = canWrite && sortedCols.length > 0 && !debouncedQ && to >= total;

  return (
    <PageTransition>
      {/* Header */}
      <div className="mb-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            to="/tables"
            className="mb-1 flex items-center gap-1 text-2xs text-content-faint hover:text-content"
          >
            <ArrowLeft className="h-3 w-3" />
            Jadvallar
          </Link>
          <div className="flex items-center gap-2.5">
            {canWrite ? (
              <input
                defaultValue={table.name}
                onBlur={(e) => renameTable(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                className="min-w-0 rounded-sm bg-transparent text-xl font-semibold tracking-tight text-content outline-none hover:bg-surface-overlay focus:bg-surface-overlay focus:px-1"
              />
            ) : (
              <h1 className="text-xl font-semibold tracking-tight text-content">{table.name}</h1>
            )}
            <Badge variant={table.section === "shared" ? "neutral" : "accent"}>
              {SECTION_LABELS[table.section]}
            </Badge>
            {table.is_archived && (
              <Badge variant="warning">
                <Archive className="h-3 w-3" />
                Arxiv
              </Badge>
            )}
          </div>
          {table.description && (
            <p className="mt-1 text-sm text-content-muted">{table.description}</p>
          )}
        </div>

        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <div className="relative w-56">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-content-faint" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Qidirish"
              className="h-9 pl-9"
              aria-label="Qatorlar orasida qidirish"
            />
          </div>
          {canWrite && (
            <>
              <Button variant="secondary" onClick={() => setColDialog({ open: true, column: null })}>
                <Plus className="h-4 w-4" />
                Ustun
              </Button>
              <Button onClick={() => setNewRowOpen(true)} disabled={sortedCols.length === 0}>
                <Plus className="h-4 w-4" />
                Qator
              </Button>
            </>
          )}
          <Dropdown>
            <DropdownTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Jadval sozlamalari">
                <Settings2 className="h-4 w-4" />
              </Button>
            </DropdownTrigger>
            <DropdownContent align="end">
              <DropdownItem onSelect={() => setExportOpen(true)}>
                <Download className="h-3.5 w-3.5" />
                Eksport / yuklab olish
              </DropdownItem>
              {canWrite && sortedCols.length > 0 && (
                <DropdownItem onSelect={() => setImportOpen(true)}>
                  <Upload className="h-3.5 w-3.5" />
                  CSV import
                </DropdownItem>
              )}
              {(canWrite || table.is_archived) &&
                writableSectionsFor(user?.role ?? "viewer").includes(table.section) &&
                user?.role !== "viewer" && (
                  <>
                    <DropdownSeparator />
                    <DropdownItem onSelect={toggleArchive}>
                      {table.is_archived ? (
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
                  </>
                )}
              {isSuper && (
                <DropdownItem destructive onSelect={() => setPendingDeleteTable(true)}>
                  <Trash2 className="h-3.5 w-3.5" />
                  Jadvalni o'chirish
                </DropdownItem>
              )}
            </DropdownContent>
          </Dropdown>
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}

      {canWrite && sortedCols.length > 0 && (
        <p className="mb-2 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-2xs text-content-faint">
          <Kbd>↑</Kbd>
          <Kbd>↓</Kbd>
          <Kbd>←</Kbd>
          <Kbd>→</Kbd>
          harakat ·
          <Kbd>Enter</Kbd>
          tahrir ·
          <Kbd>Del</Kbd>
          tozalash ·
          <Kbd>Tab</Kbd>
          keyingi katak
        </p>
      )}

      {/* Grid */}
      <div
        ref={gridRef}
        tabIndex={0}
        onKeyDown={onGridKeyDown}
        className="overflow-x-auto rounded-lg border border-line outline-none focus-visible:ring-1 focus-visible:ring-accent/40"
      >
        <table className="w-full min-w-max border-collapse text-sm">
          <thead className="bg-surface-raised">
            <tr>
              <th className="w-10 border-b border-line px-2 py-2 text-2xs font-medium text-content-faint">
                #
              </th>
              {sortedCols.map((col, i) => {
                const meta = typeMeta(col.type);
                const sortState =
                  sort === `${col.key}:asc` ? "asc" : sort === `${col.key}:desc` ? "desc" : null;
                return (
                  <th
                    key={col.id}
                    onDragEnter={() => canWrite && setDragOverCol(i)}
                    onDragOver={(e) => canWrite && e.preventDefault()}
                    className={cn(
                      "group min-w-[160px] max-w-[360px] border-b border-l border-line px-3 py-2 text-left align-middle font-medium",
                      dragOverCol === i && "bg-accent-soft",
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <meta.icon className="h-3.5 w-3.5 shrink-0 text-content-faint" />
                      <button
                        onClick={() => cycleSort(col.key)}
                        draggable={canWrite}
                        onDragStart={() => (dragCol.current = i)}
                        onDragEnd={() => {
                          if (dragCol.current !== null && dragOverCol !== null) {
                            void reorderColumns(dragCol.current, dragOverCol);
                          }
                          dragCol.current = null;
                          setDragOverCol(null);
                        }}
                        className={cn(
                          "flex items-center gap-1 truncate text-content-muted hover:text-content",
                          canWrite && "cursor-grab active:cursor-grabbing",
                        )}
                        title="Saralash · sudrab tartiblang"
                      >
                        <span className="truncate">{col.label}</span>
                        {col.config.required && <span className="text-danger">*</span>}
                        {sortState === "asc" && <ChevronUp className="h-3 w-3" />}
                        {sortState === "desc" && <ChevronDown className="h-3 w-3" />}
                      </button>
                      {canWrite && (
                        <Dropdown>
                          <DropdownTrigger asChild>
                            <button
                              className="ml-auto rounded p-0.5 text-content-faint opacity-0 transition-opacity hover:bg-surface-overlay hover:text-content group-hover:opacity-100"
                              aria-label={`${col.label} ustuni menyusi`}
                            >
                              <ChevronDown className="h-3.5 w-3.5" />
                            </button>
                          </DropdownTrigger>
                          <DropdownContent align="end">
                            <DropdownItem onSelect={() => setColDialog({ open: true, column: col })}>
                              <Pencil className="h-3.5 w-3.5" />
                              Tahrirlash
                            </DropdownItem>
                            <DropdownItem disabled={i === 0} onSelect={() => reorderColumns(i, i - 1)}>
                              <MoveLeft className="h-3.5 w-3.5" />
                              Chapga
                            </DropdownItem>
                            <DropdownItem
                              disabled={i === sortedCols.length - 1}
                              onSelect={() => reorderColumns(i, i + 1)}
                            >
                              <MoveRight className="h-3.5 w-3.5" />
                              O'ngga
                            </DropdownItem>
                            <DropdownItem destructive onSelect={() => setPendingDeleteCol(col)}>
                              <Trash2 className="h-3.5 w-3.5" />
                              O'chirish
                            </DropdownItem>
                          </DropdownContent>
                        </Dropdown>
                      )}
                    </div>
                  </th>
                );
              })}
              <th className="w-24 border-b border-l border-line px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {showSkeleton && (
              <tr>
                <td colSpan={sortedCols.length + 2} className="py-10 text-center">
                  <Spinner className="mx-auto" />
                </td>
              </tr>
            )}

            {!showSkeleton && sortedCols.length === 0 && (
              <tr>
                <td colSpan={2} className="py-16 text-center text-sm text-content-muted">
                  {canWrite ? "Boshlash uchun ustun qo'shing." : "Ustunlar yo'q."}
                </td>
              </tr>
            )}

            {!showSkeleton && sortedCols.length > 0 && rows.length === 0 && !showInlineAdd && (
              <tr>
                <td
                  colSpan={sortedCols.length + 2}
                  className="py-16 text-center text-sm text-content-muted"
                >
                  {debouncedQ ? "Hech narsa topilmadi." : "Qatorlar yo'q."}
                </td>
              </tr>
            )}

            {!showSkeleton &&
              rows.map((row, rIdx) => (
                <tr key={row.id} className="group hover:bg-surface-overlay/40">
                  <td className="border-b border-line px-2 py-0 text-center text-2xs tabular-nums text-content-faint">
                    {offset + rIdx + 1}
                  </td>
                  {sortedCols.map((col, cIdx) => {
                    const isEditing =
                      editing?.rowId === row.id && editing.key === col.key;
                    const isActive = active?.r === rIdx && active.c === cIdx;
                    const cellKey = `${row.id}:${col.key}`;
                    const saving = savingCell === cellKey;
                    const errHere =
                      cellError?.rowId === row.id && cellError.key === col.key
                        ? cellError.msg
                        : null;
                    return (
                      <td
                        key={col.id}
                        onClick={() => {
                          setActive({ r: rIdx, c: cIdx });
                          gridRef.current?.focus();
                        }}
                        className={cn(
                          "relative border-b border-l border-line p-0 align-top",
                          isActive && !isEditing && "outline outline-2 -outline-offset-2 outline-accent",
                          errHere && "outline outline-1 outline-danger",
                        )}
                      >
                        {isEditing && col.type !== "boolean" ? (
                          <div className="relative min-h-[36px]">
                            <CellEditor
                              col={col}
                              value={row.data[col.key] ?? null}
                              users={users}
                              onCommit={(v, mode) => commitCell(row, col, v, mode)}
                              onCancel={() => {
                                setEditing(null);
                                gridRef.current?.focus();
                              }}
                            />
                          </div>
                        ) : col.type === "boolean" ? (
                          <div className="flex min-h-[36px] items-center px-3 py-1.5">
                            <input
                              type="checkbox"
                              disabled={!canWrite || saving}
                              checked={!!row.data[col.key]}
                              onChange={(e) => commitCell(row, col, e.target.checked)}
                              className="h-4 w-4 rounded border-line-strong accent-[hsl(var(--accent))] disabled:opacity-50"
                            />
                          </div>
                        ) : (
                          <button
                            type="button"
                            disabled={!canWrite}
                            onClick={() =>
                              canWrite && setEditing({ rowId: row.id, key: col.key })
                            }
                            className={cn(
                              "flex min-h-[36px] w-full items-start px-3 py-1.5 text-left",
                              canWrite && "hover:bg-surface-overlay/60",
                              saving && "opacity-50",
                            )}
                          >
                            <CellDisplay
                              col={col}
                              value={row.data[col.key]}
                              usernameById={usernameById}
                            />
                          </button>
                        )}
                        {errHere && <CellErrorTooltip message={errHere} />}
                      </td>
                    );
                  })}
                  <td className="border-b border-l border-line px-1 py-1">
                    <div className="flex items-center justify-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-content-faint"
                        onClick={() => setHistoryRowId(row.id)}
                        aria-label="Tarix"
                        title="Tarix"
                      >
                        <History className="h-3.5 w-3.5" />
                      </Button>
                      {canWrite && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-content-faint"
                            onClick={() => duplicateRow(row)}
                            aria-label="Nusxalash"
                            title="Nusxalash"
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-content-faint hover:text-danger"
                            onClick={() => setPendingDeleteRow(row)}
                            aria-label="Qatorni o'chirish"
                            title="O'chirish"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}

            {/* Inline yangi qator */}
            {!showSkeleton && showInlineAdd && (
              <tr className="bg-surface-raised/40">
                <td className="border-b border-line px-2 text-center text-content-faint">
                  <Plus className="mx-auto h-3.5 w-3.5" />
                </td>
                {sortedCols.map((col) => (
                  <td key={col.id} className="border-b border-l border-line p-1 align-top">
                    <RowFieldInput
                      compact
                      col={col}
                      value={newRow[col.key]}
                      users={users}
                      onChange={(v) => setNewRow((d) => ({ ...d, [col.key]: v }))}
                    />
                    {newRowErrors[col.key] && (
                      <p className="mt-0.5 text-2xs text-danger">{newRowErrors[col.key]}</p>
                    )}
                  </td>
                ))}
                <td className="border-b border-l border-line px-1 py-1 text-center">
                  <Button
                    size="icon"
                    className="h-7 w-7"
                    loading={newRowSaving}
                    onClick={commitNewRow}
                    aria-label="Qatorni saqlash"
                    title="Saqlash"
                  >
                    {!newRowSaving && <Check className="h-3.5 w-3.5" />}
                  </Button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="mt-3 flex items-center justify-between text-xs text-content-muted">
        <span>
          {from}–{to} / {total}
          {rowsLoading && !showSkeleton && <span className="ml-2 text-content-faint">yangilanmoqda…</span>}
        </span>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Oldingi
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={to >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Keyingi
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Dialogs */}
      <ColumnDialog
        tableId={tableId}
        column={colDialog.column}
        open={colDialog.open}
        onOpenChange={(v) => setColDialog((s) => ({ ...s, open: v }))}
        onSaved={() => {
          void loadTable();
          void loadRows();
        }}
      />
      <NewRowDialog
        table={table}
        open={newRowOpen}
        onOpenChange={setNewRowOpen}
        onCreated={() => {
          void loadRows();
          void loadTable();
        }}
      />
      <ImportDialog
        tableId={tableId}
        columns={sortedCols}
        open={importOpen}
        onOpenChange={setImportOpen}
        onDone={() => {
          void loadRows();
          void loadTable();
        }}
      />
      <ExportDialog
        tableId={tableId}
        tableName={table.name}
        q={debouncedQ}
        sort={sort}
        open={exportOpen}
        onOpenChange={setExportOpen}
      />
      <RowHistoryDialog
        tableId={tableId}
        rowId={historyRowId}
        columns={sortedCols}
        canWrite={canWrite}
        onOpenChange={(v) => !v && setHistoryRowId(null)}
        onRestored={() => {
          void loadRows();
          void loadTable();
        }}
      />
      <ConfirmDialog
        open={pendingDeleteCol !== null}
        onOpenChange={(v) => !v && setPendingDeleteCol(null)}
        title={`"${pendingDeleteCol?.label}" ustunini o'chirish`}
        description="Ustun ta'rifi va barcha qatorlardagi shu ustun qiymatlari o'chiriladi. Bu amalni ortga qaytarib bo'lmaydi."
        confirmLabel="O'chirish"
        variant="danger"
        onConfirm={async () => {
          if (pendingDeleteCol) await deleteColumn(pendingDeleteCol);
        }}
      />
      <ConfirmDialog
        open={pendingDeleteRow !== null}
        onOpenChange={(v) => !v && setPendingDeleteRow(null)}
        title="Qatorni o'chirish"
        description="Qator o'chiriladi (tarixda snapshot saqlanadi)."
        confirmLabel="O'chirish"
        variant="danger"
        onConfirm={async () => {
          if (pendingDeleteRow) await deleteRow(pendingDeleteRow);
        }}
      />
      <ConfirmDialog
        open={pendingDeleteTable}
        onOpenChange={setPendingDeleteTable}
        title={`"${table.name}" jadvalini butunlay o'chirish`}
        description="Jadval, barcha ustunlar, qatorlar va tarix butunlay o'chiriladi. Ortga qaytarib bo'lmaydi. (Arxivga o'tkazishni ko'rib chiqing.)"
        confirmLabel="Butunlay o'chirish"
        variant="danger"
        onConfirm={deleteTable}
      />
    </PageTransition>
  );
}
