import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api, apiError, fieldErrors } from "@/lib/api";
import { useDirectory } from "@/lib/directory";
import { defaultCellValue } from "@/lib/dynamic";
import type { DynamicColumn, DynamicTableDetail } from "@/lib/types";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/input";
import { RowFieldInput } from "@/pages/tables/cells";

export function NewRowDialog({
  table,
  open,
  onOpenChange,
  onCreated,
}: {
  table: DynamicTableDetail;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: () => void;
}) {
  const { users } = useDirectory();
  const [data, setData] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      const seed: Record<string, unknown> = {};
      for (const col of table.columns) {
        const dv = defaultCellValue(col);
        if (dv !== "" && dv !== false) seed[col.key] = dv;
      }
      setData(seed);
      setErrors({});
      setFormError(null);
    }
  }, [open, table.columns]);

  const set = (key: string, v: unknown) => setData((d) => ({ ...d, [key]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});
    setFormError(null);
    setLoading(true);
    try {
      const clean: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(data)) {
        if (v !== "" && v !== undefined) clean[k] = v;
      }
      await api.post(`/tables/${table.id}/rows`, { data: clean });
      toast.success("Qator qo'shildi");
      onCreated();
      onOpenChange(false);
    } catch (err) {
      const fe = fieldErrors(err);
      if (fe) setErrors(fe);
      else setFormError(apiError(err, "Qatorni saqlab bo'lmadi"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        title="Yangi qator"
        description="Maydonlarni to'ldiring. Majburiy maydonlar * bilan belgilangan."
      >
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="max-h-[55vh] space-y-3 overflow-auto pr-1">
            {table.columns.length === 0 && (
              <p className="text-xs text-content-faint">
                Avval kamida bitta ustun qo'shing.
              </p>
            )}
            {table.columns.map((col) => (
              <Field
                key={col.id}
                col={col}
                value={data[col.key]}
                error={errors[col.key]}
                users={users}
                onChange={(v) => set(col.key, v)}
              />
            ))}
          </div>

          {formError && (
            <div role="alert" className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Bekor qilish
            </Button>
            <Button type="submit" loading={loading} disabled={table.columns.length === 0}>
              Qo'shish
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  col,
  value,
  error,
  users,
  onChange,
}: {
  col: DynamicColumn;
  value: unknown;
  error?: string;
  users: { id: string; username: string }[];
  onChange: (v: unknown) => void;
}) {
  const req = !!col.config.required;
  return (
    <div>
      <Label htmlFor={`f-${col.id}`}>
        {col.label}
        {req && <span className="text-danger"> *</span>}
      </Label>
      <RowFieldInput col={col} value={value} users={users} onChange={onChange} />
      {error && <p className="mt-1 text-2xs text-danger">{error}</p>}
    </div>
  );
}
