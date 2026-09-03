import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  apiError,
  runRefresh,
  setAccessToken,
  setOnAuthLost,
} from "@/lib/api";
import type { LoginResponse, Role, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  status: "loading" | "authenticated" | "anonymous";
  login: (username: string, password: string) => Promise<LoginResponse>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  const refreshMe = useCallback(async () => {
    const { data } = await api.get<User>("/users/me");
    setUser(data);
    setStatus("authenticated");
  }, []);

  const bootstrap = useCallback(async () => {
    // Sahifa yangilanganda: cookie orqali access token tiklashga urinamiz
    const token = await runRefresh();
    if (!token) {
      setStatus("anonymous");
      return;
    }
    try {
      await refreshMe();
    } catch {
      setAccessToken(null);
      setStatus("anonymous");
    }
  }, [refreshMe]);

  useEffect(() => {
    setOnAuthLost(() => {
      setAccessToken(null);
      setUser(null);
      setStatus("anonymous");
    });
    void bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const { data } = await api.post<LoginResponse>("/auth/login", {
        username,
        password,
      });
      setAccessToken(data.access_token);
      setUser(data.user);
      setStatus("authenticated");
      return data;
    } catch (err) {
      throw new Error(apiError(err, "Kirishda xatolik"));
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* muhim emas */
    }
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  const hasRole = useCallback(
    (...roles: Role[]) => (user ? roles.includes(user.role) : false),
    [user],
  );

  const value = useMemo<AuthState>(
    () => ({ user, status, login, logout, refreshMe, hasRole }),
    [user, status, login, logout, refreshMe, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider ichida ishlatilishi kerak");
  return ctx;
}
