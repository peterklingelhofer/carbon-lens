// Cloudflare Worker entry: serves the built SPA from ./dist AND proxies API
// paths to the Render backend, so the browser only ever makes SAME-ORIGIN
// requests. This removes CORS entirely and, crucially, stops privacy extensions
// / Firefox Enhanced Tracking Protection from blocking the (otherwise
// cross-origin, third-party) API calls — those tools block by request domain,
// and now every request is first-party to the page's own origin.

const API_ORIGIN = "https://carbonlens-gssa.onrender.com";

// Paths owned by the backend API rather than the static site.
function isApiPath(pathname) {
  return (
    pathname === "/health" ||
    pathname.startsWith("/health/") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/ws/") ||
    pathname === "/ready" ||
    pathname === "/docs" ||
    pathname === "/redoc" ||
    pathname === "/openapi.json" ||
    pathname === "/metrics"
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (isApiPath(url.pathname)) {
      // Forward method, headers, and body unchanged to the backend. fetch() uses
      // the target URL's host for the connection, so this lands on Render.
      const target = API_ORIGIN + url.pathname + url.search;
      return fetch(new Request(target, request));
    }

    // Everything else: the static SPA. env.ASSETS applies the configured
    // single-page-application fallback (client routes -> index.html).
    return env.ASSETS.fetch(request);
  },
};
