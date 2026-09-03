import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  Copy,
  Download,
  Link2,
  Link2Off,
  Loader2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import type { ExportFormat, ExportJob, ShareLink } from "@/lib/types";
import { formatDateTime, relativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const FORMATS: { value: ExportFormat; label: string; hint: string }[] = [
  { value: "csv", label: "CSV", hint: "Excel/Google Sheets" },
  { value: "xlsx", label: "XLSX", hint: "Excel (formatli)" },
  { value: "json", label: "JSON", hint: "Dasturiy ishlov" },
];

const STATUS: Record<
  ExportJob["status"],
  { label: string; variant: "neutral" | "success" | "danger" | "warning" }
> = {
  pending: { label: "Navbatda", variant: "neutral" },
  running: { label: "Ishlamoqda", variant: "warning" },
  done: { label: "Tayyor", variant: "success" },
  failed: { label: "Xato", variant: "danger" },
  cancelled: { label: "Bekor qilindi", variant: "neutral" },
};

function humanSize(n: number | null): string {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

async function downloadViaApi(
  url: string,
  params: Record<string, unknown> | undefined,
  fallbackName: string,
) {
  const res = await api.get(url, { params, responseType: "blob" });
  const cd = (res.headers["content-disposition"] as string | undefined) ?? "";
  const m = /filename="?([^"]+)"?/.exec(cd);
  const name = m ? m[1] : fallbackName;
  const blobUrl = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}

export function ExportDialog({
  tableId,
  tableName,
  q,
  sort,
  open,
  onOpenChange,
}: {
  tableId: string;
  tableName: string;
  q: string;
  sort: string | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [fmt, setFmt] = useState<ExportFormat>("csv");
  const [busy, setBusy] = useState<"now" | "job" | null>(null);
  const [jobs, setJobs] = useState<ExportJob[]>([]);
  const [links, setLinks] = useState<Record<string, ShareLink>>({});
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const params = {
    ...(q ? { q } : {}),
    ...(sort ? { sort } : {}),
  };

  const loadJobs = useCallback(async () => {
    try {
      const { data } = await api.get<ExportJob[]>(`/tables/${tableId}/export/jobs`);
      setJobs(data);
      return data;
    } catch (e) {
      setError(apiError(e));
      return [];
    }
  }, [tableId]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setLinks({});
    void loadJobs();
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [open, loadJobs]);

  // pending/running bo'lsa 2s'da bir yangilab turamiz
  useEffect(() => {
    if (!open) return;
    const active = jobs.some((j) => j.status === "pending" || j.status === "running");
    if (!active) return;
    pollRef.current = setTimeout(() => void loadJobs(), 2000);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [open, jobs, loadJobs]);

  async function exportNow() {
    setError(null);
    setBusy("now");
    try {
      await downloadViaApi(
        `/tables/${tableId}/export`,
        { ...params, format: fmt },
        `${tableName || "jadval"}.${fmt}`,
      );
      toast.success("Yuklab olindi");
    } catch {
      setError("Yuklab bo'lmadi. Katta jadval uchun fon job yarating.");
    } finally {
      setBusy(null);
    }
  }

  async function createJob() {
    setError(null);
    setBusy("job");
    try {
      await api.post(`/tables/${tableId}/export/jobs`, null, {
        params: { ...params, format: fmt },
      });
      toast.success("Fon eksport boshlandi");
      await loadJobs();
    } catch (e) {
      setError(apiError(e, "Job yaratib bo'lmadi"));
    } finally {
      setBusy(null);
    }
  }

  async function cancel(job: ExportJob) {
    try {
      await api.post(`/exports/${job.id}/cancel`);
      await loadJobs();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function download(job: ExportJob) {
    try {
      await downloadViaApi(
        `/exports/${job.id}/download`,
        undefined,
        job.file_name ?? `${job.id}.${job.format}`,
      );
      void loadJobs();
    } catch (e) {
      toast.error(apiError(e, "Yuklab bo'lmadi"));
    }
  }

  async function share(job: ExportJob) {
    try {
      const { data } = await api.post<ShareLink>(`/exports/${job.id}/share`);
      // Havolani doim joriy origin'ga bog'laymiz (proksi ortida base_url
      // port/sxemani noto'g'ri qo'yishi mumkin).
      let url = data.url;
      try {
        const u = new URL(data.url);
        url = `${window.location.origin}${u.pathname}${u.search}`;
      } catch {
        /* data.url yaroqsiz bo'lsa asl qiymatni qoldiramiz */
      }
      setLinks((l) => ({ ...l, [job.id]: { ...data, url } }));
      await loadJobs();
    } catch (e) {
      toast.error(apiError(e, "Havola yaratib bo'lmadi"));
    }
  }

  async function revoke(job: ExportJob) {
    try {
      await api.post(`/exports/${job.id}/share/revoke`);
      setLinks((l) => {
        const n = { ...l };
        delete n[job.id];
        return n;
      });
      await loadJobs();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  function copy(text: string, key: string) {
    navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(key);
        setTimeout(() => setCopied((c) => (c === key ? null : c)), 1500);
      },
      () => toast.error("Nusxalab bo'lmadi"),
    );
  }

  const hasFilter = q || sort;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        className="max-w-xl"
        title="Eksport / yuklab olish"
        description="CSV/XLSX/JSON — hozir yoki fon job orqali. Tayyor faylni vaqtli havola bilan ulashish mumkin."
      >
        <div className="space-y-4">
          <div>
            <Label>Format</Label>
            <div className="grid grid-cols-3 gap-2">
              {FORMATS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => setFmt(f.value)}
                  className={cn(
                    "rounded-md border px-3 py-2 text-left transition-all",
                    fmt === f.value
                      ? "border-accent bg-accent-soft"
                      : "border-line-strong hover:border-line",
                  )}
                >
                  <span className="block text-xs font-semibold text-content">{f.label}</span>
                  <span className="block text-2xs text-content-faint">{f.hint}</span>
                </button>
              ))}
            </div>
          </div>

          <p className="text-2xs text-content-faint">
            {hasFilter ? (
              <>
                Joriy ko'rinish bilan:
                {q && <> qidiruv <span className="text-content-muted">"{q}"</span></>}
                {q && sort && " ·"}
                {sort && <> saralash <span className="text-content-muted">{sort}</span></>}
              </>
            ) : (
              "Barcha qatorlar, jadval tartibida."
            )}
          </p>

          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              loading={busy === "now"}
              disabled={fmt === "xlsx" || busy !== null}
              onClick={exportNow}
              title={fmt === "xlsx" ? "XLSX faqat fon job orqali" : undefined}
            >
              <Download className="h-4 w-4" />
              Hozir yuklab olish
            </Button>
            <Button
              className="flex-1"
              loading={busy === "job"}
              disabled={busy !== null}
              onClick={createJob}
            >
              Fon job yaratish
            </Button>
          </div>
          {fmt === "xlsx" && (
            <p className="-mt-2 text-2xs text-content-faint">
              XLSX katta bo'lishi mumkin — faqat fon job orqali.
            </p>
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

          {/* Job tarixi */}
          <div>
            <Label>Fon eksportlar</Label>
            {jobs.length === 0 ? (
              <p className="rounded-md border border-dashed border-line-strong py-3 text-center text-2xs text-content-faint">
                Hali yo'q
              </p>
            ) : (
              <ul className="max-h-[38vh] space-y-1.5 overflow-y-auto pr-1">
                {jobs.map((job) => {
                  const st = STATUS[job.status];
                  const link = links[job.id];
                  return (
                    <li
                      key={job.id}
                      className="rounded-md border border-line bg-surface-raised p-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="neutral">{job.format.toUpperCase()}</Badge>
                        <Badge variant={st.variant}>
                          {(job.status === "running" || job.status === "pending") && (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          )}
                          {st.label}
                        </Badge>
                        <span className="ml-auto text-2xs text-content-faint">
                          {relativeTime(job.created_at)}
                        </span>
                      </div>

                      {job.status === "done" && (
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-content-faint">
                          <span>{job.row_count ?? 0} qator</span>
                          <span>{humanSize(job.file_size_bytes)}</span>
                          {job.download_count > 0 && <span>{job.download_count}× yuklandi</span>}
                          {job.checksum_sha256 && (
                            <span
                              className="font-mono"
                              title={`SHA-256: ${job.checksum_sha256}`}
                            >
                              #{job.checksum_sha256.slice(0, 8)}
                            </span>
                          )}
                        </div>
                      )}
                      {job.status === "failed" && job.error_message && (
                        <p className="mt-1 text-2xs text-danger">{job.error_message}</p>
                      )}

                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {job.status === "done" && (
                          <>
                            <Button size="sm" className="h-7 text-2xs" onClick={() => download(job)}>
                              <Download className="h-3 w-3" />
                              Yuklab olish
                            </Button>
                            {!link && !job.has_share_link && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-2xs"
                                onClick={() => share(job)}
                              >
                                <Link2 className="h-3 w-3" />
                                Ulashish
                              </Button>
                            )}
                            {!link && job.has_share_link && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 text-2xs"
                                  onClick={() => share(job)}
                                >
                                  <Link2 className="h-3 w-3" />
                                  Yangi havola
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 text-2xs text-content-faint hover:text-danger"
                                  onClick={() => revoke(job)}
                                >
                                  <Link2Off className="h-3 w-3" />
                                  Bekor
                                </Button>
                              </>
                            )}
                          </>
                        )}
                        {(job.status === "pending" || job.status === "running") && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-2xs text-content-faint hover:text-danger"
                            onClick={() => cancel(job)}
                          >
                            <X className="h-3 w-3" />
                            Bekor qilish
                          </Button>
                        )}
                      </div>

                      {link && (
                        <div className="mt-2 space-y-1 rounded border border-accent/30 bg-accent/5 p-2">
                          <p className="text-2xs text-content-muted">
                            Vaqtli havola — {formatDateTime(link.expires_at)} gacha. Tizimga
                            kirmasdan yuklab olinadi.
                          </p>
                          <div className="flex gap-1">
                            <input
                              readOnly
                              value={link.url}
                              onFocus={(e) => e.currentTarget.select()}
                              className="min-w-0 flex-1 rounded border border-line-strong bg-surface-raised px-2 py-1 font-mono text-2xs text-content outline-none"
                            />
                            <Button
                              size="sm"
                              variant="secondary"
                              className="h-7 shrink-0 text-2xs"
                              onClick={() => copy(link.url, job.id)}
                            >
                              {copied === job.id ? (
                                <Check className="h-3 w-3" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                              {copied === job.id ? "Nusxalandi" : "Nusxa"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 shrink-0 text-2xs text-content-faint hover:text-danger"
                              onClick={() => revoke(job)}
                            >
                              <Link2Off className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Yopish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
