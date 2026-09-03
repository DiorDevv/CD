import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertCircle, KeyRound, Check } from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";

const MIN_LEN = 10;

const rules = [
  { test: (p: string) => p.length >= MIN_LEN, label: `Kamida ${MIN_LEN} ta belgi` },
  { test: (p: string) => /[a-z]/.test(p), label: "Kamida bitta kichik harf" },
  { test: (p: string) => /[A-Z]/.test(p), label: "Kamida bitta katta harf" },
  { test: (p: string) => /\d/.test(p), label: "Kamida bitta raqam" },
  { test: (p: string) => !/\s/.test(p) && p.length > 0, label: "Bo'sh joysiz" },
];

export function ChangePasswordPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const forced = user?.must_change_password ?? false;

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passed = rules.every((r) => r.test(next));
  const matches = next.length > 0 && next === confirm;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!matches) {
      setError("Yangi parollar mos kelmadi");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      toast.success("Parol yangilandi. Iltimos qaytadan kiring.");
      await logout();
      navigate("/login", { replace: true });
    } catch (err) {
      setError(apiError(err, "Parolni o'zgartirib bo'lmadi"));
      setLoading(false);
    }
  }

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-canvas px-4">
      <div className="pointer-events-none absolute inset-0 aurora opacity-70" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-[420px]"
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-accent text-accent-fg shadow-glow">
            <KeyRound className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold tracking-tight">
            Parolni o'zgartirish
          </h1>
          <p className="mt-1 text-sm text-content-muted">
            {forced
              ? "Birinchi kirish — davom etishdan oldin vaqtinchalik parolni almashtiring."
              : "Yangi parol o'rnating. Barcha faol sessiyalar tugatiladi."}
          </p>
        </div>

        <div className="rounded-lg border border-line-strong bg-surface/80 p-6 shadow-overlay backdrop-blur-xl">
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="current">Joriy (vaqtinchalik) parol</Label>
              <Input
                id="current"
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div>
              <Label htmlFor="next">Yangi parol</Label>
              <Input
                id="next"
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                aria-invalid={next.length > 0 && !passed}
                required
              />
            </div>
            <div>
              <Label htmlFor="confirm">Yangi parolni tasdiqlang</Label>
              <Input
                id="confirm"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                aria-invalid={confirm.length > 0 && !matches}
                required
              />
            </div>

            <ul className="space-y-1.5 pt-1" aria-live="polite">
              {rules.map((r) => {
                const ok = r.test(next);
                return (
                  <li
                    key={r.label}
                    className={`flex items-center gap-2 text-xs transition-colors ${
                      ok ? "text-success" : "text-content-faint"
                    }`}
                  >
                    <span
                      className={`grid h-3.5 w-3.5 place-items-center rounded-full border ${
                        ok ? "border-success bg-success/15" : "border-line-strong"
                      }`}
                    >
                      {ok && <Check className="h-2.5 w-2.5" />}
                    </span>
                    {r.label}
                  </li>
                );
              })}
            </ul>

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

            <Button
              type="submit"
              size="lg"
              className="w-full"
              loading={loading}
              disabled={!passed || !matches || !current}
            >
              Parolni saqlash
            </Button>
          </form>
        </div>
      </motion.div>
    </div>
  );
}
