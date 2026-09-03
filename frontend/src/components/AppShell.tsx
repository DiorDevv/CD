import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  ChevronsUpDown,
  LogOut,
  ScrollText,
  ShieldAlert,
  Users,
  LayoutDashboard,
  DatabaseZap,
  Eye,
  Table2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS, roleAccent, type Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ConfirmDialog";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV: Record<Role, NavItem[]> = {
  super_admin: [
    { to: "/super-admin/dashboard", label: "Boshqaruv paneli", icon: LayoutDashboard },
    { to: "/super-admin/users", label: "Foydalanuvchilar", icon: Users },
    { to: "/super-admin/audit-logs", label: "Audit jurnali", icon: ScrollText },
    { to: "/tables", label: "Jadvallar", icon: Table2 },
  ],
  soc_admin: [
    { to: "/soc/dashboard", label: "SOC paneli", icon: ShieldAlert },
    { to: "/tables", label: "Jadvallar", icon: Table2 },
  ],
  dlp_admin: [
    { to: "/dlp/dashboard", label: "DLP paneli", icon: DatabaseZap },
    { to: "/tables", label: "Jadvallar", icon: Table2 },
  ],
  viewer: [
    { to: "/viewer/dashboard", label: "Umumiy ko'rinish", icon: Eye },
    { to: "/tables", label: "Jadvallar", icon: Table2 },
  ],
};

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [confirmLogout, setConfirmLogout] = useState(false);

  if (!user) return null;
  const items = NAV[user.role];

  return (
    <div
      data-role={roleAccent(user.role)}
      className="flex min-h-screen bg-canvas text-content"
    >
      {/* ---- Sidebar ---- */}
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-line bg-surface/60 backdrop-blur-xl">
        <div className="flex h-14 items-center gap-2.5 px-5 border-b border-line">
          <div className="grid h-7 w-7 place-items-center rounded-md bg-accent text-accent-fg">
            <Activity className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight">Sentinel</p>
            <p className="text-2xs text-content-faint">SOC / DLP Platform</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          <p className="px-3 pb-1.5 pt-2 text-2xs font-medium uppercase tracking-wider text-content-faint">
            Bo'limlar
          </p>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
                  isActive
                    ? "bg-accent-soft text-content"
                    : "text-content-muted hover:bg-surface-overlay hover:text-content",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute left-0 top-1.5 h-[calc(100%-12px)] w-0.5 rounded-full bg-accent"
                      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    />
                  )}
                  <item.icon className="h-4 w-4 shrink-0" />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* ---- User box ---- */}
        <div className="border-t border-line p-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-2">
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-surface-overlay text-xs font-semibold uppercase text-content">
              {user.username.slice(0, 2)}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-sm font-medium">{user.username}</p>
              <p className="truncate text-2xs text-content-faint">
                {ROLE_LABELS[user.role]}
              </p>
            </div>
            <ChevronsUpDown className="h-3.5 w-3.5 text-content-faint" />
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="mt-1 w-full justify-start"
            onClick={() => setConfirmLogout(true)}
          >
            <LogOut className="h-4 w-4" />
            Chiqish
          </Button>
        </div>
      </aside>

      {/* ---- Main ---- */}
      <div className="ml-60 flex min-h-screen flex-1 flex-col">
        <main className="flex-1 px-8 py-7">
          {/* key -> har marshrutda yumshoq "enter" animatsiyasi qayta o'ynaydi */}
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      <ConfirmDialog
        open={confirmLogout}
        onOpenChange={setConfirmLogout}
        title="Tizimdan chiqish"
        description="Joriy sessiya tugatiladi va qaytadan kirish talab qilinadi."
        confirmLabel="Chiqish"
        variant="danger"
        onConfirm={async () => {
          await logout();
          navigate("/login", { replace: true });
        }}
      />
    </div>
  );
}
