import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const normalizeTarget = (value: string | undefined) =>
  value?.trim() || "http://localhost:8000";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
      proxy: {
        "/api": {
          target: normalizeTarget(env.VITE_API_TARGET),
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
