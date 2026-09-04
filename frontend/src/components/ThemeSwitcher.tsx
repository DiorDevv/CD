import { Moon, Sun, SunMoon } from "lucide-react";
import { useTheme, THEME_LABELS, type Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const ICON: Record<Theme, typeof Sun> = {
  light: Sun,
  dim: SunMoon,
  dark: Moon,
};

const ORDER: Theme[] = ["light", "dim", "dark"];

export function ThemeSwitcher({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();

  return (
    <div
      role="radiogroup"
      aria-label="Ko'rinish mavzusi"
      className={cn(
        "flex items-center gap-0.5 rounded-md border border-line-strong bg-surface-raised p-0.5",
        className,
      )}
    >
      {ORDER.map((t) => {
        const Icon = ICON[t];
        const on = theme === t;
        return (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={on}
            title={THEME_LABELS[t]}
            onClick={() => setTheme(t)}
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-[5px] transition-colors",
              on
                ? "bg-accent-soft text-accent"
                : "text-content-faint hover:text-content",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        );
      })}
    </div>
  );
}
