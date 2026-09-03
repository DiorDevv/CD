import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Ban,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  KeyRound,
  Plus,
  Search,
  Trash2,
  UserPlus,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { User, UserPage } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { PageTransition } from "@/components/PageTransition";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { TableRowsSkeleton } from "@/components/ui/skeleton";
import { StatusBadge, RoleBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CreateUserDialog } from "@/pages/superadmin/CreateUserDialog";
import { ResetPasswordDialog } from "@/pages/superadmin/ResetPasswordDialog";

const PAGE_SIZE = 20;

export function UsersPage() {
  const { user: me } = useAuth();
  const [page, setPage] = useState<UserPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<User | null>(null);
  const [pendingReset, setPendingReset] = useState<User | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const firstLoad = useRef(true);

  // Qidiruvni debounce qilamiz (server tomonda filtrlanadi)
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQ(q.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<UserPage>("/admin/users", {
        params: {
          limit: PAGE_SIZE,
          offset,
          ...(debouncedQ ? { q: debouncedQ } : {}),
        },
      });
      setPage(data);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoading(false);
      firstLoad.current = false;
    }
  }, [offset, debouncedQ]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleBlock(u: User) {
    setBusyId(u.id);
    const action = u.is_active ? "block" : "unblock";
    try {
      await api.patch(`/admin/users/${u.id}/${action}`);
      toast.success(
        u.is_active ? `"${u.username}" bloklandi` : `"${u.username}" faollashtirildi`,
      );
      await load();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(u: User) {
    try {
      await api.delete(`/admin/users/${u.id}`);
      toast.success(`"${u.username}" o'chirildi`);
      // Oxirgi qatorni o'chirgan bo'lsak — oldingi sahifaga o'tamiz
      if (page && page.items.length === 1 && offset > 0) {
        setOffset(Math.max(0, offset - PAGE_SIZE));
      } else {
        await load();
      }
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  const items = page?.items ?? [];
  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const showSkeleton = loading && firstLoad.current;

  return (
    <PageTransition>
      <PageHeader
        title="Foydalanuvchilar"
        description="SOC / DLP adminlari va kuzatuvchilarni yaratish va boshqarish."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Yangi foydalanuvchi
          </Button>
        }
      />

      <div className="mb-4 flex items-center gap-3">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-content-faint" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Username bo'yicha qidirish"
            className="h-9 pl-9"
            aria-label="Foydalanuvchi nomi bo'yicha qidirish"
          />
        </div>
        {page && (
          <span className="text-xs text-content-faint">{total} ta yozuv</span>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
        >
          {error}
        </div>
      )}

      <Card className="overflow-hidden border-0 shadow-none">
        <Table>
          <THead>
            <TR className="hover:bg-transparent">
              <TH>Foydalanuvchi</TH>
              <TH>Rol</TH>
              <TH>Holat</TH>
              <TH>Yaratilgan</TH>
              <TH className="text-right">Amallar</TH>
            </TR>
          </THead>
          <TBody>
            {showSkeleton && <TableRowsSkeleton rows={6} cols={5} />}

            {!showSkeleton && items.length === 0 && (
              <tr>
                <td colSpan={5} className="py-16 text-center">
                  <UserPlus className="mx-auto mb-2 h-6 w-6 text-content-faint" />
                  <p className="text-sm text-content-muted">
                    Foydalanuvchi topilmadi
                  </p>
                </td>
              </tr>
            )}

            {!showSkeleton &&
              items.map((u, i) => {
                const isSelf = u.id === me?.id;
                return (
                  <motion.tr
                    key={u.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      delay: Math.min(i * 0.03, 0.3),
                      duration: 0.2,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                    className="border-b border-line transition-colors last:border-0 hover:bg-surface-overlay/60"
                  >
                    <TD>
                      <div className="flex items-center gap-3">
                        <div className="grid h-8 w-8 place-items-center rounded-full bg-surface-overlay text-2xs font-semibold uppercase">
                          {u.username.slice(0, 2)}
                        </div>
                        <div className="leading-tight">
                          <span className="font-medium">{u.username}</span>
                          {isSelf && (
                            <span className="ml-2 text-2xs text-content-faint">
                              (siz)
                            </span>
                          )}
                        </div>
                      </div>
                    </TD>
                    <TD>
                      <RoleBadge role={u.role} />
                    </TD>
                    <TD>
                      <StatusBadge user={u} />
                    </TD>
                    <TD className="text-xs text-content-muted">
                      {formatDateTime(u.created_at)}
                    </TD>
                    <TD>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={isSelf || busyId === u.id}
                          loading={busyId === u.id}
                          onClick={() => toggleBlock(u)}
                        >
                          {u.is_active ? (
                            <>
                              <Ban className="h-3.5 w-3.5" />
                              Bloklash
                            </>
                          ) : (
                            <>
                              <CircleCheck className="h-3.5 w-3.5" />
                              Faollashtirish
                            </>
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-content-faint hover:text-content"
                          disabled={isSelf}
                          onClick={() => setPendingReset(u)}
                          title="Parolni tiklash"
                          aria-label={`${u.username} parolini tiklash`}
                        >
                          <KeyRound className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-content-faint hover:text-danger"
                          disabled={isSelf}
                          onClick={() => setPendingDelete(u)}
                          title="O'chirish"
                          aria-label={`${u.username} ni o'chirish`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TD>
                  </motion.tr>
                );
              })}
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
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Oldingi
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={to >= total || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Keyingi
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <CreateUserDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={load}
      />

      <ResetPasswordDialog
        user={pendingReset}
        onOpenChange={(v) => !v && setPendingReset(null)}
        onDone={load}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(v) => !v && setPendingDelete(null)}
        title={`"${pendingDelete?.username}" ni o'chirish`}
        description="Bu amalni ortga qaytarib bo'lmaydi. Foydalanuvchi va uning sessiyalari butunlay o'chiriladi."
        confirmLabel="O'chirish"
        variant="danger"
        onConfirm={async () => {
          if (pendingDelete) await remove(pendingDelete);
        }}
      />
    </PageTransition>
  );
}
