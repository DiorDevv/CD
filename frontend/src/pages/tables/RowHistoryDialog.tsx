import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useDirectory } from "@/lib/directory";
import { cellText } from "@/lib/dynamic";
import { formatDateTime } from "@/lib/utils";
import type { DynamicColumn, RowRevision } from "@/lib/types";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

const ACTION_LABEL: Record<string, string> = {
  create: "Yaratildi",
  update: "O'zgartirildi",
  delete: "O'chirildi",
};
const ACTION_VARIANT = {
  create: "accent",
  update: "neutral",
  delete: "danger",
} as const;

export function RowHistoryDialog({
  tableId,
  rowId,
  columns,
  canWrite = false,
  onOpenChange,
  onRestored,
}: {
  tableId: string;
  rowId: string | null;
  columns: DynamicColumn[];
  canWrite?: boolean;
  onOpenChange: (v: boolean) => void;
  onRestored?: () => void;
}) {
  const open = rowId !== null;
  const { byId } = useDirectory();
  const usernameById = new Map([...byId].map(([id, u]) => [id, u.username]));
  const [revs, setRevs] = useState<RowRevision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !rowId) return;
    setRevs(null);
    setError(null);
    api
      .get<RowRevision[]>(`/tables/${tableId}/rows/${rowId}/revisions`)
      .then((r) => setRevs(r.data))
      .catch((e) => setError(apiError(e)));
  }, [open, rowId, tableId]);

  async function restore(rev: RowRevision) {
    if (!rowId) return;
    setRestoring(rev.id);
    try {
      await api.post(
        `/tables/${tableId}/rows/${rowId}/revisions/${rev.id}/restore`,
      );
      toast.success("Qator shu holatga tiklandi");
      onRestored?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(apiError(e, "Tiklab bo'lmadi"));
    } finally {
      setRestoring(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        title="Qator tarixi"
        description="Ushbu qator ustidagi barcha o'zgarishlar (eng yangisi tepada)."
      >
        {error && (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        )}
        {!revs && !error && (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        )}
        {revs && revs.length === 0 && (
          <p className="py-6 text-center text-xs text-content-faint">Yozuv yo'q</p>
        )}
        <ol className="max-h-[60vh] space-y-3 overflow-auto">
          {revs?.map((r, idx) => (
            <li key={r.id} className="rounded-md border border-line bg-surface-raised p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <Badge variant={ACTION_VARIANT[r.action]}>
                  {ACTION_LABEL[r.action] ?? r.action}
                  {idx === 0 && r.action !== "delete" ? " · joriy" : ""}
                </Badge>
                <span className="text-2xs text-content-faint">
                  {formatDateTime(r.changed_at)}
                  {r.changed_by && usernameById.get(r.changed_by)
                    ? ` · ${usernameById.get(r.changed_by)}`
                    : ""}
                </span>
              </div>
              {r.data && (
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  {columns.map((c) => (
                    <div key={c.id} className="contents">
                      <dt className="text-content-faint">{c.label}</dt>
                      <dd className="truncate text-content">
                        {cellText(c, r.data?.[c.key], usernameById) || "—"}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
              {canWrite && r.data && idx !== 0 && (
                <div className="mt-2 flex justify-end border-t border-line pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-2xs"
                    loading={restoring === r.id}
                    onClick={() => restore(r)}
                  >
                    <RotateCcw className="h-3 w-3" />
                    Shu holatga tiklash
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ol>
      </DialogContent>
    </Dialog>
  );
}
