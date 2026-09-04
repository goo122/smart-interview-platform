import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const normalizeTarget = (value: string | undefined) =>
  value?.trim() || "http://127.0.0.1:8000";

const vendorChunk = (id: string) => {
  const moduleId = id.replaceAll("\\", "/");
  if (!moduleId.includes("/node_modules/")) return undefined;
  if (
    /\/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler)\//.test(
      moduleId,
    )
  ) {
    return "vendor-react";
  }
  if (
    /\/node_modules\/(@reduxjs|react-redux|@tanstack|immer|redux|reselect)\//.test(
      moduleId,
    )
  ) {
    return "vendor-state";
  }
  if (
    /\/node_modules\/(framer-motion|motion-dom|motion-utils)\//.test(moduleId)
  ) {
    return "vendor-motion";
  }
  if (/\/node_modules\/(react-pdf|pdfjs-dist)\//.test(moduleId)) {
    return "vendor-pdf";
  }
  if (/\/node_modules\/(@radix-ui|lucide-react)\//.test(moduleId)) {
    return "vendor-ui";
  }
  return "vendor-misc";
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: vendorChunk,
        },
      },
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
