import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Upload } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { csvValueToCell, parseCsv } from "@/lib/dynamic";
import type { DynamicColumn } from "@/lib/types";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/input";

interface BulkResult {
  created: number;
  failed: number;
  errors: { index: number; errors: Record<string, string> }[];
}

export function ImportDialog({
  tableId,
  columns,
  open,
  onOpenChange,
  onDone,
}: {
  tableId: string;
  columns: DynamicColumn[];
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onDone: () => void;
}) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BulkResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setText("");
      setResult(null);
      setError(null);
    }
  }, [open]);

  const parsed = useMemo(() => {
    if (!text.trim()) return null;
    const grid = parseCsv(text);
    if (grid.length < 2) return { header: grid[0] ?? [], mapping: [], rows: [] as Record<string, unknown>[] };
    const header = grid[0].map((h) => h.trim());
    const byLabel = new Map(columns.map((c) => [c.label.trim().toLowerCase(), c]));
    const mapping = header.map((h) => byLabel.get(h.toLowerCase()) ?? null);
    const rows = grid.slice(1).map((line) => {
      const data: Record<string, unknown> = {};
      mapping.forEach((col, i) => {
        if (!col) return;
        const v = csvValueToCell(col, line[i] ?? "");
        if (v !== undefined) data[col.key] = v;
      });
      return data;
    });
    return { header, mapping, rows };
  }, [text, columns]);

  const matched = parsed?.mapping.filter(Boolean).length ?? 0;

  function pickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  async function run() {
    if (!parsed || parsed.rows.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post<BulkResult>(`/tables/${tableId}/rows/bulk`, {
        rows: parsed.rows.slice(0, 1000),
      });
      setResult(data);
      if (data.created > 0) {
        toast.success(`${data.created} ta qator import qilindi`);
        onDone();
      }
      if (data.failed === 0) onOpenChange(false);
    } catch (e) {
      setError(apiError(e, "Import muvaffaqiyatsiz"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        className="max-w-xl"
        title="CSV import"
        description="Birinchi qator — ustun sarlavhalari. Sarlavhalar ustun nomlari bilan solishtiriladi."
      >
        <div className="space-y-3">
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-line-strong py-3 text-xs text-content-muted hover:border-accent">
            <Upload className="h-3.5 w-3.5" />
            CSV fayl tanlash
            <input type="file" accept=".csv,text/csv" onChange={pickFile} className="hidden" />
          </label>

          <div>
            <Label>yoki CSV matnini joylashtiring</Label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              placeholder={`Sarlavha,Darajasi\nFishing hujum,high`}
              className="w-full resize-y rounded-md border border-line-strong bg-surface-raised p-2 font-mono text-xs text-content outline-none focus:border-accent"
            />
          </div>

          {parsed && (
            <div className="rounded-md border border-line bg-surface-raised p-3 text-xs">
              <p className="text-content-muted">
                {parsed.rows.length} ta qator · {matched}/{parsed.header.length} ustun mos keldi
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {parsed.header.map((h, i) => (
                  <span
                    key={i}
                    className={
                      parsed.mapping[i]
                        ? "rounded border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-accent"
                        : "rounded border border-line-strong px-1.5 py-0.5 text-content-faint line-through"
                    }
                  >
                    {h || "(bo'sh)"}
                  </span>
                ))}
              </div>
              {matched === 0 && (
                <p className="mt-1.5 text-warning">
                  Hech bir sarlavha ustun nomiga mos kelmadi.
                </p>
              )}
            </div>
          )}

          {result && (
            <div className="rounded-md border border-line bg-surface-raised p-3 text-xs">
              <p className="flex items-center gap-1.5 text-success">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {result.created} ta qo'shildi
              </p>
              {result.failed > 0 && (
                <div className="mt-1.5 text-danger">
                  <p>{result.failed} ta qator xato:</p>
                  <ul className="mt-1 space-y-0.5">
                    {result.errors.slice(0, 8).map((er) => (
                      <li key={er.index}>
                        {er.index + 2}-qator: {Object.values(er.errors).join("; ")}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Yopish
          </Button>
          <Button
            type="button"
            loading={loading}
            disabled={!parsed || parsed.rows.length === 0 || matched === 0}
            onClick={run}
          >
            {parsed ? `${parsed.rows.length} qatorni import qilish` : "Import qilish"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
