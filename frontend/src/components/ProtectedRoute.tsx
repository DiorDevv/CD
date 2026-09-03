import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { FullPageSpinner } from "@/components/ui/spinner";
import { ROLE_HOME, type Role } from "@/lib/types";

interface Props {
  /** Ruxsat etilgan rollar. Bo'sh bo'lsa — faqat autentifikatsiya talab qilinadi. */
  roles?: Role[];
}

/**
 * FRONTEND himoyasi — bu FAQAT UX uchun. Haqiqiy himoya backend'da (dependency'lar).
 *
 *  - autentifikatsiya yo'q            -> /login
 *  - must_change_password            -> /change-password (boshqa hech qayerga emas)
 *  - roli mos emas                   -> o'z dashboard'iga qaytariladi
 */
export function ProtectedRoute({ roles }: Props) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageSpinner label="Sessiya tekshirilmoqda" />;

  if (status === "anonymous" || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  if (roles && roles.length > 0 && !roles.includes(user.role)) {
    return <Navigate to={ROLE_HOME[user.role]} replace />;
  }

  return <Outlet />;
}
