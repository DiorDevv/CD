import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Users,
  ShieldCheck,
  CircleSlash,
  ScrollText,
  ArrowUpRight,
} from "lucide-react";
import { api, apiError } from "@/lib/api";
import type { AuditLog, AuditLogPage, UserPage } from "@/lib/types";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ACTION_LABELS } from "@/pages/superadmin/auditMeta";
import { relativeTime } from "@/lib/utils";

interface Stat {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
}

interface Counts {
  total: number;
  active: number;
  blocked: number;
}

export function SuperAdminDashboardPage() {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [logs, setLogs] = useState<AuditLog[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<UserPage>("/admin/users", { params: { limit: 1 } }),
      api.get<UserPage>("/admin/users", { params: { limit: 1, is_active: true } }),
      api.get<UserPage>("/admin/users", { params: { limit: 1, is_active: false } }),
      api.get<AuditLogPage>("/admin/audit-logs", { params: { limit: 8 } }),
    ])
      .then(([all, act, blk, l]) => {
        setCounts({
          total: all.data.total,
          active: act.data.total,
          blocked: blk.data.total,
        });
        setLogs(l.data.items);
      })
      .catch((e) => setError(apiError(e)));
  }, []);

  const stats: Stat[] = [
    { label: "Jami foydalanuvchi", value: counts?.total ?? 0, icon: Users, tone: "text-accent" },
    { label: "Faol", value: counts?.active ?? 0, icon: ShieldCheck, tone: "text-success" },
    { label: "Bloklangan", value: counts?.blocked ?? 0, icon: CircleSlash, tone: "text-danger" },
  ];

  return (
    <PageTransition>
      <PageHeader
        title="Boshqaruv paneli"
        description="Tizim foydalanuvchilari va so'nggi faoliyat ko'rinishi."
      />

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {stats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          >
            <Card>
              <CardContent className="flex items-center justify-between">
                <div>
                  <p className="text-2xs uppercase tracking-wider text-content-faint">
                    {s.label}
                  </p>
                  {counts ? (
                    <p className="mt-1 text-2xl font-semibold tabular-nums">
                      {s.value}
                    </p>
                  ) : (
                    <Skeleton className="mt-2 h-7 w-12" />
                  )}
                </div>
                <s.icon className={`h-5 w-5 ${s.tone}`} />
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card className="mt-4">
        <CardContent className="p-0">
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <div className="flex items-center gap-2 text-sm font-medium">
              <ScrollText className="h-4 w-4 text-content-muted" />
              So'nggi faoliyat
            </div>
            <Link
              to="/super-admin/audit-logs"
              className="flex items-center gap-1 text-xs text-content-muted transition-colors hover:text-content"
            >
              Barchasi
              <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          <ul className="divide-y divide-line">
            {!logs &&
              Array.from({ length: 5 }).map((_, i) => (
                <li key={i} className="px-5 py-3">
                  <Skeleton className="h-4 w-2/3" />
                </li>
              ))}
            {logs?.map((log) => (
              <li
                key={log.id}
                className="flex items-center justify-between px-5 py-3 text-sm"
              >
                <span className="flex items-center gap-2.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                  <span className="text-content">
                    {ACTION_LABELS[log.action] ?? log.action}
                  </span>
                  {log.details?.username != null && (
                    <span className="font-mono text-xs text-content-faint">
                      {String(log.details.username)}
                    </span>
                  )}
                </span>
                <span className="text-2xs text-content-faint">
                  {relativeTime(log.created_at)}
                </span>
              </li>
            ))}
            {logs?.length === 0 && (
              <li className="px-5 py-6 text-center text-xs text-content-faint">
                Hozircha yozuv yo'q
              </li>
            )}
          </ul>
        </CardContent>
      </Card>
    </PageTransition>
  );
}
