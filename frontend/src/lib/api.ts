import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000/api";

/**
 * Access token FAQAT xotirada saqlanadi (localStorage EMAS — XSS himoyasi).
 * Refresh token backend tomonidan httpOnly cookie sifatida boshqariladi.
 */
let accessToken: string | null = null;
let onAuthLost: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}
export function getAccessToken() {
  return accessToken;
}
export function setOnAuthLost(cb: () => void) {
  onAuthLost = cb;
}

export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // refresh cookie yuborilishi uchun
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// --- Access token muddati tugaganda avtomatik refresh ---
let refreshing: Promise<string | null> | null = null;

async function runRefresh(): Promise<string | null> {
  try {
    const res = await axios.post<{ access_token: string }>(
      `${BASE_URL}/auth/refresh`,
      {},
      { withCredentials: true },
    );
    accessToken = res.data.access_token;
    return accessToken;
  } catch {
    accessToken = null;
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as
      | (AxiosRequestConfig & { _retried?: boolean })
      | undefined;
    const url = original?.url ?? "";
    const isAuthRoute =
      url.includes("/auth/login") ||
      url.includes("/auth/refresh") ||
      url.includes("/auth/change-password");

    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !isAuthRoute
    ) {
      original._retried = true;
      refreshing = refreshing ?? runRefresh();
      const token = await refreshing;
      refreshing = null;

      if (token) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization =
          `Bearer ${token}`;
        return api(original);
      }
      onAuthLost?.();
    }
    return Promise.reject(error);
  },
);

/** Backend'ning `detail` maydonidan foydalanuvchiga ko'rsatiladigan xabar ajratadi. */
export function apiError(err: unknown, fallback = "Xatolik yuz berdi"): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
    // Qator validatsiyasi: { errors: { <key>: "<xabar>" } }
    if (detail && typeof detail === "object" && detail.errors) {
      const vals = Object.values(detail.errors as Record<string, string>);
      if (vals.length) return vals.join("; ");
    }
  }
  return fallback;
}

/** Qator validatsiya xatolarini ustun-kaliti -> xabar ko'rinishida qaytaradi. */
export function fieldErrors(err: unknown): Record<string, string> | null {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (detail && typeof detail === "object" && detail.errors) {
      return detail.errors as Record<string, string>;
    }
  }
  return null;
}

/** HTTP status kodini qaytaradi (masalan 409 ni alohida ko'rsatish uchun). */
export function apiStatus(err: unknown): number | null {
  return axios.isAxiosError(err) ? (err.response?.status ?? null) : null;
}

export { runRefresh };
