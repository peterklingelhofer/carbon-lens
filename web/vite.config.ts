/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  build: {
    // The globe's three.js + globe.gl is unavoidably large but is lazy-loaded into
    // its own CarbonGlobe-*.js chunk (only fetched on /globe), so it doesn't touch
    // initial load. Raise the warning above that known chunk so the build stays
    // clean while still flagging anything genuinely oversized.
    chunkSizeWarningLimit: 2000,
  },
  test: {
    // jsdom so component tests can render React; setup file wires RTL cleanup.
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
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
