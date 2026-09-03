import type { Config } from "tailwindcss";

/**
 * DIZAYN TIZIMI — barcha token'lar shu yerda.
 * Ranglar CSS o'zgaruvchilari orqali (src/index.css) beriladi, shuning uchun
 * role bo'yicha aksent (SOC=ko'k, DLP=binafsha, Super Admin=neytral) bitta
 * joyda almashadi.
 */
const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "2rem" },
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        canvas: "hsl(var(--canvas) / <alpha-value>)",
        surface: {
          DEFAULT: "hsl(var(--surface) / <alpha-value>)",
          raised: "hsl(var(--surface-raised) / <alpha-value>)",
          overlay: "hsl(var(--surface-overlay) / <alpha-value>)",
        },
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        content: {
          DEFAULT: "hsl(var(--content) / <alpha-value>)",
          muted: "hsl(var(--content-muted) / <alpha-value>)",
          faint: "hsl(var(--content-faint) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          fg: "hsl(var(--accent-fg) / <alpha-value>)",
          soft: "hsl(var(--accent) / 0.12)",
        },
        success: "hsl(var(--success) / <alpha-value>)",
        danger: "hsl(var(--danger) / <alpha-value>)",
        warning: "hsl(var(--warning) / <alpha-value>)",
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.24), 0 1px 3px 0 rgb(0 0 0 / 0.12)",
        overlay: "0 16px 48px -12px rgb(0 0 0 / 0.6), 0 0 0 1px var(--line-strong)",
        glow: "0 0 0 1px hsl(var(--accent) / 0.4), 0 0 32px -4px hsl(var(--accent) / 0.35)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        shimmer: "shimmer 1.6s infinite",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
