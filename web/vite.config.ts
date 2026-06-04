import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Mirror the production Cloudflare Worker proxy (worker.js): forward API
    // paths to the local backend so the app makes same-origin relative requests
    // in dev too.
    proxy: {
      // trailing slash so the SPA route /api-explorer isn't swallowed by the proxy
      "/api/": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/ready": "http://localhost:8000",
      "/docs": "http://localhost:8000",
      "/redoc": "http://localhost:8000",
      "/openapi.json": "http://localhost:8000",
      "/ws/": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
