import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // trailing slash so the SPA route /api-explorer isn't swallowed by the proxy
      // (matches the production nginx `location /api/` behavior)
      "/api/": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/ws/": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
