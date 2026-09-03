import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // `.env*` fayllar + haqiqiy muhit o'zgaruvchilari (Docker `environment:` / build `args`)
  const fileEnv = loadEnv(mode, process.cwd(), "");
  const apiBaseUrl =
    process.env.VITE_API_BASE_URL ||
    fileEnv.VITE_API_BASE_URL ||
    "http://localhost:8000/api";

  const isDocker = process.env.DOCKER === "1" || process.env.CI === "1";

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    // `import.meta.env.VITE_API_BASE_URL` ni har doim aniq qiymatga bog'laymiz —
    // shunda Docker `environment:` orqali berilgan qiymat ham ishlaydi.
    define: {
      "import.meta.env.VITE_API_BASE_URL": JSON.stringify(apiBaseUrl),
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      // Docker bind-mount ostida HMR ishlashi uchun (lokal ishda kerak emas)
      watch: isDocker ? { usePolling: true } : undefined,
    },
  };
});
