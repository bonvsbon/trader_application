import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Dev proxy forwards /api and /ws to the FastAPI backend so the browser can use
// relative URLs (no CORS juggling in development).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
