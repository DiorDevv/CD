import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Check, Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import type { User, UserCreatedResponse } from "@/lib/types";
import { MIN_PASSWORD, randomPassword } from "@/lib/password";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

interface Props {
  user: User | null;
  onOpenChange: (v: boolean) => void;
  onDone: () => void;
}

export function ResetPasswordDialog({ user, onOpenChange, onDone }: Props) {
  const open = user !== null;
  const [password, setPassword] = useState(randomPassword());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UserCreatedResponse | null>(null);
  const [copied, setCopied] = useState(false);

  // Har ochilishda yangi holat
  useEffect(() => {
    if (open) {
      setPassword(randomPassword());
      setError(null);
      setResult(null);
      setCopied(false);
    }
  }, [open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post<UserCreatedResponse>(
        `/admin/users/${user.id}/reset-password`,
        { temporary_password: password },
      );
      setResult(data);
      onDone();
      toast.success(`"${user.username}" paroli tiklandi`);
    } catch (err) {
      setError(apiError(err, "Parolni tiklab bo'lmadi"));
    } finally {
      setLoading(false);
    }
  }

  async function copyCreds() {
    if (!result) return;
    await navigator.clipboard.writeText(
      `username: ${result.user.username}\nparol: ${result.temporary_password}`,
    );
    setCopied(true);
    toast.success("Nusxalandi");
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        open={open}
        title={result ? "Parol tiklandi" : `"${user?.username}" parolini tiklash`}
        description={
          result
            ? "Yangi vaqtinchalik parolni foydalanuvchiga xavfsiz kanal orqali yuboring. Parol qayta ko'rsatilmaydi."
            : "Yangi vaqtinchalik parol o'rnatiladi. Foydalanuvchining barcha sessiyalari tugatiladi va u keyingi kirishda parolni almashtiradi."
        }
      >
        {result ? (
          <div className="space-y-3">
            <div className="rounded-md border border-line-strong bg-surface-raised p-4 font-mono text-sm">
              <div className="flex justify-between py-1">
                <span className="text-content-faint">username</span>
                <span>{result.user.username}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-content-faint">yangi parol</span>
                <span>{result.temporary_password}</span>
              </div>
            </div>
            <DialogFooter>
              <Button variant="secondary" onClick={copyCreds}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                Nusxalash
              </Button>
              <Button onClick={() => onOpenChange(false)}>Yopish</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="rp-pass">Yangi vaqtinchalik parol</Label>
              <div className="flex gap-2">
                <Input
                  id="rp-pass"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="font-mono"
                  minLength={MIN_PASSWORD}
                  required
                />
                <Button
                  type="button"
                  variant="secondary"
                  size="icon"
                  onClick={() => setPassword(randomPassword())}
                  title="Yangi parol generatsiya qilish"
                  aria-label="Yangi parol generatsiya qilish"
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {error && (
              <motion.div
                role="alert"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
              >
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Bekor qilish
              </Button>
              <Button
                type="submit"
                variant="danger"
                loading={loading}
                disabled={password.length < MIN_PASSWORD}
              >
                Parolni tiklash
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
