import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Copy, RefreshCw, Check } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import type { Role, UserCreatedResponse } from "@/lib/types";
import { ROLE_LABELS } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { MIN_PASSWORD, randomPassword } from "@/lib/password";

const CREATABLE: Role[] = ["soc_admin", "dlp_admin", "viewer"];

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: () => void;
}

export function CreateUserDialog({ open, onOpenChange, onCreated }: Props) {
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<Role>("soc_admin");
  const [password, setPassword] = useState(randomPassword());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UserCreatedResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const roleRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function reset() {
    setUsername("");
    setRole("soc_admin");
    setPassword(randomPassword());
    setError(null);
    setResult(null);
    setCopied(false);
  }

  function handleOpenChange(v: boolean) {
    onOpenChange(v);
    if (!v) setTimeout(reset, 200);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post<UserCreatedResponse>("/admin/users", {
        username: username.trim(),
        temporary_password: password,
        role,
      });
      setResult(data);
      onCreated();
      toast.success(`"${data.user.username}" yaratildi`);
    } catch (err) {
      setError(apiError(err, "Foydalanuvchi yaratilmadi"));
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
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        open={open}
        title={result ? "Foydalanuvchi yaratildi" : "Yangi foydalanuvchi"}
        description={
          result
            ? "Quyidagi ma'lumotlarni foydalanuvchiga xavfsiz kanal orqali yuboring. Parol qayta ko'rsatilmaydi."
            : "Username va vaqtinchalik parol bering. Foydalanuvchi birinchi kirishda parolni almashtiradi."
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
                <span className="text-content-faint">parol</span>
                <span>{result.temporary_password}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-content-faint">rol</span>
                <span>{ROLE_LABELS[result.user.role]}</span>
              </div>
            </div>
            <DialogFooter>
              <Button variant="secondary" onClick={copyCreds}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                Nusxalash
              </Button>
              <Button onClick={() => handleOpenChange(false)}>Yopish</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="cu-username">Foydalanuvchi nomi</Label>
              <Input
                id="cu-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="3–64 belgi: harf, raqam, . _ -"
                pattern="[a-zA-Z0-9._-]{3,64}"
                autoFocus
                required
              />
            </div>

            <div>
              <span id="cu-role-label" className="mb-1.5 block text-xs font-medium tracking-wide text-content-muted">
                Rol
              </span>
              <div
                role="radiogroup"
                aria-labelledby="cu-role-label"
                className="grid grid-cols-3 gap-2"
                onKeyDown={(e) => {
                  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
                  e.preventDefault();
                  const cur = CREATABLE.indexOf(role);
                  const next =
                    e.key === "ArrowRight"
                      ? (cur + 1) % CREATABLE.length
                      : (cur - 1 + CREATABLE.length) % CREATABLE.length;
                  setRole(CREATABLE[next]);
                  roleRefs.current[next]?.focus();
                }}
              >
                {CREATABLE.map((r, i) => (
                  <button
                    key={r}
                    ref={(el) => {
                      roleRefs.current[i] = el;
                    }}
                    type="button"
                    role="radio"
                    aria-checked={role === r}
                    tabIndex={role === r ? 0 : -1}
                    onClick={() => setRole(r)}
                    className={`rounded-md border px-3 py-2 text-xs font-medium transition-all ${
                      role === r
                        ? "border-accent bg-accent-soft text-content"
                        : "border-line-strong text-content-muted hover:border-line hover:text-content"
                    }`}
                  >
                    {ROLE_LABELS[r]}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label htmlFor="cu-pass">Vaqtinchalik parol</Label>
              <div className="flex gap-2">
                <Input
                  id="cu-pass"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="font-mono"
                  minLength={MIN_PASSWORD}
                  aria-describedby="cu-pass-hint"
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
              <p id="cu-pass-hint" className="mt-1.5 text-2xs text-content-faint">
                Kamida {MIN_PASSWORD} belgi, katta va kichik harf hamda raqam.
                Foydalanuvchi birinchi kirishda uni almashtiradi.
              </p>
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
              <Button
                type="button"
                variant="ghost"
                onClick={() => handleOpenChange(false)}
              >
                Bekor qilish
              </Button>
              <Button
                type="submit"
                loading={loading}
                disabled={password.length < MIN_PASSWORD || username.trim().length < 3}
              >
                Yaratish
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
