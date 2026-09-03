import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Archive, Columns3, Database, Plus, Rows3 } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  SECTION_LABELS,
  writableSectionsFor,
  type DynamicTable,
  type TablePage,
} from "@/lib/types";
import { relativeTime } from "@/lib/utils";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { NewTableDialog } from "@/pages/tables/NewTableDialog";

export function TablesListPage() {
  const { user } = useAuth();
  const canCreate = user ? writableSectionsFor(user.role).length > 0 : false;
  const [tables, setTables] = useState<DynamicTable[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

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

  const grouped = groupBySection(tables ?? []);

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
              {items.map((t, i) => (
                <motion.div
                  key={t.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.25), duration: 0.2 }}
                >
                  <Link to={`/tables/${t.id}`}>
                    <Card className="h-full transition-colors hover:border-line-strong hover:bg-surface-raised">
                      <CardContent className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
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
                      </CardContent>
                    </Card>
                  </Link>
                </motion.div>
              ))}
            </div>
          </div>
        ))}

      <NewTableDialog open={createOpen} onOpenChange={setCreateOpen} />
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
