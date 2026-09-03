import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Filter } from "lucide-react";
import { api, apiError } from "@/lib/api";
import type { AuditLog, AuditLogPage as Page } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { TableRowsSkeleton } from "@/components/ui/skeleton";
import { ACTION_LABELS, ACTION_VARIANT, ALL_ACTIONS } from "@/pages/superadmin/auditMeta";

const PAGE_SIZE = 25;

export function AuditLogsPage() {
  const [page, setPage] = useState<Page | null>(null);
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<Page>("/admin/audit-logs", {
        params: {
          limit: PAGE_SIZE,
          offset,
          ...(action ? { action } : {}),
        },
      });
      setPage(data);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoading(false);
    }
  }, [offset, action]);

  useEffect(() => {
    void load();
  }, [load]);

  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <PageTransition>
      <PageHeader
        title="Audit jurnali"
        description="Tizimdagi barcha muhim amallar — kim, qachon, qayerdan."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 text-xs text-content-faint">
          <Filter className="h-3.5 w-3.5" />
          Amal turi:
        </div>
        <button
          onClick={() => {
            setAction("");
            setOffset(0);
          }}
          className={`rounded-full border px-2.5 py-1 text-2xs font-medium transition-colors ${
            action === ""
              ? "border-accent bg-accent-soft text-content"
              : "border-line-strong text-content-muted hover:text-content"
          }`}
        >
          Barchasi
        </button>
        {ALL_ACTIONS.map((a) => (
          <button
            key={a}
            onClick={() => {
              setAction(a);
              setOffset(0);
            }}
            className={`rounded-full border px-2.5 py-1 text-2xs font-medium transition-colors ${
              action === a
                ? "border-accent bg-accent-soft text-content"
                : "border-line-strong text-content-muted hover:text-content"
            }`}
          >
            {ACTION_LABELS[a]}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}

      <Card className="border-0 shadow-none">
        <Table>
          <THead>
            <TR className="hover:bg-transparent">
              <TH>Vaqt</TH>
              <TH>Amal</TH>
              <TH>Tafsilotlar</TH>
              <TH>IP manzil</TH>
            </TR>
          </THead>
          <TBody>
            {loading && <TableRowsSkeleton rows={8} cols={4} />}

            {!loading && page?.items.length === 0 && (
              <tr>
                <td colSpan={4} className="py-16 text-center text-sm text-content-muted">
                  Ushbu filtr bo'yicha yozuv yo'q
                </td>
              </tr>
            )}

            {!loading &&
              page?.items.map((log: AuditLog, i) => (
                <motion.tr
                  key={log.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    delay: Math.min(i * 0.025, 0.25),
                    duration: 0.2,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  className="border-b border-line transition-colors last:border-0 hover:bg-surface-overlay/60"
                >
                  <TD className="whitespace-nowrap font-mono text-xs text-content-muted">
                    {formatDateTime(log.created_at)}
                  </TD>
                  <TD>
                    <Badge variant={ACTION_VARIANT[log.action] ?? "neutral"}>
                      {ACTION_LABELS[log.action] ?? log.action}
                    </Badge>
                  </TD>
                  <TD className="max-w-md">
                    {log.details ? (
                      <code className="text-2xs text-content-faint">
                        {Object.entries(log.details)
                          .map(([k, v]) => `${k}=${String(v)}`)
                          .join("  ")}
                      </code>
                    ) : (
                      <span className="text-content-faint">—</span>
                    )}
                  </TD>
                  <TD className="font-mono text-xs text-content-muted">
                    {log.ip_address ?? "—"}
                  </TD>
                </motion.tr>
              ))}
          </TBody>
        </Table>
      </Card>

      <div className="mt-4 flex items-center justify-between text-xs text-content-muted">
        <span>
          {from}–{to} / {total}
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
    </PageTransition>
  );
}
