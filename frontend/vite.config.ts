import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Dev: /api is proxied to the FastAPI backend (VITE_API_URL overrides at build time).
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(path.dirname(fileURLToPath(import.meta.url)), "src") } },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          motion: ["framer-motion"],
          markdown: ["react-markdown", "remark-gfm"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.BACKEND_URL ?? "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
