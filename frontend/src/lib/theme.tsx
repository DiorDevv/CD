import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Theme = "dark" | "light" | "dim";

const THEMES: Theme[] = ["dark", "light", "dim"];
const KEY = "sentinel-theme";

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "dark" || v === "light" || v === "dim") return v;
  } catch {
    /* localStorage yo'q */
  }
  return "dark";
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

interface Ctx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  themes: Theme[];
}

const ThemeContext = createContext<Ctx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => read());

  useEffect(() => {
    apply(theme);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): Ctx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme faqat <ThemeProvider> ichida ishlaydi");
  return ctx;
}

export const THEME_LABELS: Record<Theme, string> = {
  light: "Oq",
  dim: "Yumshoq",
  dark: "Qora",
};
