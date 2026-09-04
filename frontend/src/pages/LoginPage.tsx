import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, AlertCircle, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ROLE_HOME } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(username.trim(), password);
      navigate(
        res.must_change_password ? "/change-password" : ROLE_HOME[res.user.role],
        { replace: true },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kirishda xatolik");
      setLoading(false);
    }
  }

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-canvas px-4">
      <div className="pointer-events-none absolute inset-0 aurora" />
      <div className="pointer-events-none absolute inset-0 grid-bg opacity-60" />

      <ThemeSwitcher className="absolute right-4 top-4 z-10" />

      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-[400px]"
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-accent text-accent-fg shadow-glow">
            <Activity className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold tracking-tight">Sentinel Platform</h1>
          <p className="mt-1 text-sm text-content-muted">
            SOC / DLP monitoring — xavfsiz kirish
          </p>
        </div>

        <div className="rounded-lg border border-line-strong bg-surface/80 p-6 shadow-overlay backdrop-blur-xl">
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="username">Foydalanuvchi nomi</Label>
              <Input
                id="username"
                autoFocus
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="masalan: j.doe"
                required
              />
            </div>
            <div>
              <Label htmlFor="password">Parol</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <motion.div
                role="alert"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
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
              disabled={!username || !password}
            >
              Kirish
              {!loading && <ArrowRight className="h-4 w-4" />}
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-2xs text-content-faint">
          Hisob faqat super admin tomonidan yaratiladi. Ochiq ro'yxatdan o'tish yo'q.
        </p>
      </motion.div>
    </div>
  );
}
