import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  GripVertical,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  SECTION_LABELS,
  writableSectionsFor,
  type DynamicTableDetail,
  type TableSection,
} from "@/lib/types";
import {
  draftToColumnPayload,
  newColumnDraft,
  typeMeta,
  type ColumnDraft,
} from "@/lib/dynamic";
import { TABLE_TEMPLATES, templateToDrafts } from "@/lib/tableTemplates";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ColumnFields } from "@/pages/tables/ColumnFields";
import { cn } from "@/lib/utils";

export function NewTableDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const sections = user ? writableSectionsFor(user.role) : [];

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [section, setSection] = useState<TableSection>(sections[0] ?? "shared");
  const [templateId, setTemplateId] = useState("blank");
  const [columns, setColumns] = useState<ColumnDraft[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const nameTouched = useRef(false);
  const dragIdx = useRef<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    setName("");
    setDescription("");
    setSection(sections[0] ?? "shared");
    setTemplateId("blank");
    setColumns([]);
    setExpanded(null);
    setError(null);
    nameTouched.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function applyTemplate(id: string) {
    setTemplateId(id);
    const tpl = TABLE_TEMPLATES.find((t) => t.id === id);
    if (!tpl) return;
    const drafts = templateToDrafts(tpl);
    setColumns(drafts);
    setExpanded(null);
    if (!nameTouched.current && tpl.suggestedName) setName(tpl.suggestedName);
  }

  function patchColumn(uid: string, p: Partial<ColumnDraft>) {
    setColumns((cs) => cs.map((c) => (c.uid === uid ? { ...c, ...p } : c)));
  }
  function addColumn() {
    const d = newColumnDraft();
    setColumns((cs) => [...cs, d]);
    setExpanded(d.uid);
  }
  function removeColumn(uid: string) {
    setColumns((cs) => cs.filter((c) => c.uid !== uid));
  }
  function move(from: number, to: number) {
    if (to < 0 || to >= columns.length || from === to) return;
    const next = [...columns];
    const [m] = next.splice(from, 1);
    next.splice(to, 0, m);
    setColumns(next);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    let colPayload: ReturnType<typeof draftToColumnPayload>[];
    try {
      colPayload = columns.map(draftToColumnPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ustun sozlamalari noto'g'ri");
      return;
    }

    setLoading(true);
    try {
      const { data } = await api.post<DynamicTableDetail>("/tables", {
        section,
        name: name.trim(),
        description: description.trim() || null,
        columns: colPayload.map((c, i) => ({ ...c, position: i })),
      });
      toast.success(`"${data.name}" jadvali yaratildi`);
      onOpenChange(false);
      navigate(`/tables/${data.id}`);
    } catch (err) {
      setError(apiError(err, "Jadval yaratib bo'lmadi"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        className="max-w-2xl"
        title="Yangi jadval"
        description="Shablondan boshlang yoki ustunlarni o'zingiz qo'shing."
      >
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="max-h-[64vh] space-y-4 overflow-y-auto pr-1">
            {/* Shablon */}
            <div>
              <Label>Shablon</Label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {TABLE_TEMPLATES.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => applyTemplate(t.id)}
                    className={cn(
                      "flex flex-col items-start gap-1 rounded-md border p-2.5 text-left transition-all",
                      templateId === t.id
                        ? "border-accent bg-accent-soft"
                        : "border-line-strong hover:border-line hover:bg-surface-overlay/40",
                    )}
                  >
                    <t.icon
                      className={cn(
                        "h-4 w-4",
                        templateId === t.id ? "text-accent" : "text-content-faint",
                      )}
                    />
                    <span className="text-xs font-medium text-content">{t.name}</span>
                    <span className="text-2xs text-content-faint">{t.description}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="tbl-name">Jadval nomi</Label>
                <Input
                  id="tbl-name"
                  value={name}
                  onChange={(e) => {
                    nameTouched.current = true;
                    setName(e.target.value);
                  }}
                  autoFocus
                  required
                  maxLength={120}
                  placeholder="masalan: Hodisalar jurnali"
                />
              </div>
              <div>
                <Label>Bo'lim</Label>
                <div role="radiogroup" aria-label="Bo'lim" className="grid grid-cols-3 gap-2">
                  {sections.map((s) => (
                    <button
                      key={s}
                      type="button"
                      role="radio"
                      aria-checked={section === s}
                      onClick={() => setSection(s)}
                      className={cn(
                        "rounded-md border px-2 py-2 text-xs font-medium transition-all",
                        section === s
                          ? "border-accent bg-accent-soft text-content"
                          : "border-line-strong text-content-muted hover:text-content",
                      )}
                    >
                      {SECTION_LABELS[s]}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <Label htmlFor="tbl-desc">Izoh (ixtiyoriy)</Label>
              <Input
                id="tbl-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={500}
              />
            </div>

            {/* Ustunlar */}
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <Label className="mb-0">Ustunlar ({columns.length})</Label>
                <Button type="button" variant="outline" size="sm" onClick={addColumn}>
                  <Plus className="h-3.5 w-3.5" />
                  Ustun
                </Button>
              </div>

              {columns.length === 0 && (
                <p className="rounded-md border border-dashed border-line-strong py-4 text-center text-xs text-content-faint">
                  Ustunsiz ham yaratsa bo'ladi — keyin grid ichida qo'shasiz.
                </p>
              )}

              <div className="space-y-1.5">
                {columns.map((c, i) => {
                  const meta = typeMeta(c.type);
                  const isOpen = expanded === c.uid;
                  return (
                    <div
                      key={c.uid}
                      className={cn(
                        "rounded-md border bg-surface-raised transition-colors",
                        isOpen ? "border-accent/40" : "border-line-strong",
                        dragOver === i && "ring-1 ring-accent",
                      )}
                      onDragEnter={() => setDragOver(i)}
                      onDragOver={(e) => e.preventDefault()}
                    >
                      <div className="flex items-center gap-1.5 px-2 py-1.5">
                        <span
                          draggable
                          onDragStart={() => (dragIdx.current = i)}
                          onDragEnd={() => {
                            if (dragIdx.current !== null && dragOver !== null) {
                              move(dragIdx.current, dragOver);
                            }
                            dragIdx.current = null;
                            setDragOver(null);
                          }}
                          className="cursor-grab text-content-faint"
                        >
                          <GripVertical className="h-3.5 w-3.5" />
                        </span>
                        <meta.icon className="h-3.5 w-3.5 shrink-0 text-content-faint" />
                        <button
                          type="button"
                          onClick={() => setExpanded(isOpen ? null : c.uid)}
                          aria-expanded={isOpen}
                          className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-xs"
                        >
                          <ChevronRight
                            className={cn(
                              "h-3.5 w-3.5 shrink-0 text-content-faint transition-transform",
                              isOpen && "rotate-90",
                            )}
                          />
                          <span className="truncate font-medium text-content">
                            {c.label || <span className="text-content-faint">Nomsiz ustun</span>}
                          </span>
                          {c.required && <span className="text-danger">*</span>}
                          <Badge variant="neutral" className="ml-1">
                            {meta.label}
                          </Badge>
                        </button>
                        <button
                          type="button"
                          onClick={() => move(i, i - 1)}
                          disabled={i === 0}
                          className="rounded p-0.5 text-content-faint hover:text-content disabled:opacity-30"
                        >
                          <ChevronUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => move(i, i + 1)}
                          disabled={i === columns.length - 1}
                          className="rounded p-0.5 text-content-faint hover:text-content disabled:opacity-30"
                        >
                          <ChevronDown className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeColumn(c.uid)}
                          className="rounded p-0.5 text-content-faint hover:text-danger"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      {isOpen && (
                        <div className="border-t border-line px-3 py-3">
                          <ColumnFields
                            draft={c}
                            onChange={(p) => patchColumn(c.uid, p)}
                            compact
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Bekor qilish
            </Button>
            <Button type="submit" loading={loading} disabled={name.trim().length === 0}>
              Yaratish
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
