import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import type { DynamicColumn } from "@/lib/types";
import {
  columnToDraft,
  draftToColumnPayload,
  newColumnDraft,
  type ColumnDraft,
} from "@/lib/dynamic";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ColumnFields } from "@/pages/tables/ColumnFields";

interface Props {
  tableId: string;
  column: DynamicColumn | null; // null => yangi
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSaved: () => void;
}

export function ColumnDialog({ tableId, column, open, onOpenChange, onSaved }: Props) {
  const isEdit = column !== null;
  const [draft, setDraft] = useState<ColumnDraft>(() => newColumnDraft());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setDraft(column ? columnToDraft(column) : newColumnDraft());
  }, [open, column]);

  const patch = (p: Partial<ColumnDraft>) => setDraft((d) => ({ ...d, ...p }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    let payload: ReturnType<typeof draftToColumnPayload>;
    try {
      payload = draftToColumnPayload(draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ustun sozlamalari noto'g'ri");
      return;
    }

    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        label: payload.label,
        config: payload.config,
      };
      if (!isEdit || column!.type !== payload.type) body.type = payload.type;

      if (isEdit) {
        await api.patch(`/tables/${tableId}/columns/${column!.id}`, body);
        toast.success("Ustun yangilandi");
      } else {
        await api.post(`/tables/${tableId}/columns`, body);
        toast.success("Ustun qo'shildi");
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(apiError(err, "Ustunni saqlab bo'lmadi"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        title={isEdit ? "Ustunni tahrirlash" : "Yangi ustun"}
        description="Ustun nomi va turini belgilang. Tanlov turlari uchun variantlarni qo'shing."
      >
        <form onSubmit={save} className="space-y-4" noValidate>
          <div className="max-h-[60vh] overflow-y-auto pr-1">
            <ColumnFields
              draft={draft}
              onChange={patch}
              originalType={column?.type}
            />
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
            <Button type="submit" loading={loading} disabled={draft.label.trim().length === 0}>
              {isEdit ? "Saqlash" : "Qo'shish"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
