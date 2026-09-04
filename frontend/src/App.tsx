import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { useTheme } from "@/lib/theme";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppShell } from "@/components/AppShell";
import { FullPageSpinner } from "@/components/ui/spinner";
import { ROLE_HOME } from "@/lib/types";
import { LoginPage } from "@/pages/LoginPage";
import { ChangePasswordPage } from "@/pages/ChangePasswordPage";
import { SuperAdminDashboardPage } from "@/pages/superadmin/DashboardPage";
import { UsersPage } from "@/pages/superadmin/UsersPage";
import { AuditLogsPage } from "@/pages/superadmin/AuditLogsPage";
import {
  SocDashboardPage,
  DlpDashboardPage,
  ViewerDashboardPage,
} from "@/pages/sections";
import { TablesListPage } from "@/pages/tables/TablesListPage";
import { TableGridPage } from "@/pages/tables/TableGridPage";

const ALL_ROLES = ["super_admin", "soc_admin", "dlp_admin", "viewer"] as const;

/** "/" ga kirilganda role bo'yicha to'g'ri dashboard'ga yo'naltirish */
function RootRedirect() {
  const { status, user } = useAuth();
  if (status === "loading") return <FullPageSpinner label="Yuklanmoqda" />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  return <Navigate to={ROLE_HOME[user.role]} replace />;
}

export default function App() {
  const { theme } = useTheme();
  return (
    <BrowserRouter>
      <ErrorBoundary>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* Autentifikatsiya talab qilinadi (rol cheklovi yo'q) */}
          <Route element={<ProtectedRoute />}>
            <Route path="/change-password" element={<ChangePasswordPage />} />
          </Route>

          {/* Yagona AppShell — barcha himoyalangan sahifalar shu ichida.
              Rol cheklovi ichma-ich ProtectedRoute orqali beriladi. */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route element={<ProtectedRoute roles={["super_admin"]} />}>
                <Route path="/super-admin/dashboard" element={<SuperAdminDashboardPage />} />
                <Route path="/super-admin/users" element={<UsersPage />} />
                <Route path="/super-admin/audit-logs" element={<AuditLogsPage />} />
              </Route>

              <Route element={<ProtectedRoute roles={["soc_admin", "super_admin"]} />}>
                <Route path="/soc/dashboard" element={<SocDashboardPage />} />
              </Route>

              <Route element={<ProtectedRoute roles={["dlp_admin", "super_admin"]} />}>
                <Route path="/dlp/dashboard" element={<DlpDashboardPage />} />
              </Route>

              <Route element={<ProtectedRoute roles={["viewer", "super_admin"]} />}>
                <Route path="/viewer/dashboard" element={<ViewerDashboardPage />} />
              </Route>

              {/* Dinamik jadvallar — barcha rollar (viewer read-only backend'da) */}
              <Route element={<ProtectedRoute roles={[...ALL_ROLES]} />}>
                <Route path="/tables" element={<TablesListPage />} />
                <Route path="/tables/:tableId" element={<TableGridPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="/" element={<RootRedirect />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        <Toaster
          theme={theme === "light" ? "light" : "dark"}
          position="bottom-right"
          toastOptions={{
            style: {
              background: "hsl(var(--surface-overlay))",
              border: "1px solid var(--line-strong)",
              color: "hsl(var(--content))",
            },
          }}
        />
      </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
