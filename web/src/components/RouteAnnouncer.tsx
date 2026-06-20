import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

// Per-route page titles. SPA navigation never reloads the document, so without
// this every route would keep index.html's title and a screen reader would
// announce the same name on every page. Keep in sync with Nav's routes.
const TITLES: Record<string, string> = {
  "/": "Carbon Lens - live carbon intensity for cloud regions",
  "/globe": "Carbon Globe - Carbon Lens",
  "/dashboard": "Grid Data - Carbon Lens",
  "/api-explorer": "API Explorer - Carbon Lens",
  "/compliance": "Compliance reporting - Carbon Lens",
  "/sla": "SLA monitor - Carbon Lens",
  "/scheduler": "Carbon-aware scheduler - Carbon Lens",
  "/route": "Workload routing - Carbon Lens",
  "/clean-compute": "State of clean compute - Carbon Lens",
  "/methodology": "Methodology - Carbon Lens",
  "/settings": "Status - Carbon Lens",
  "/about": "About - Carbon Lens",
};

const FALLBACK = "Carbon Lens";

// On every SPA navigation: set the document title and move focus to <main> so
// assistive tech announces the new page and keyboard focus doesn't get stranded
// on the link that was just activated. Skips the initial mount (the page already
// has focus at the top and index.html's title is correct for "/").
export function RouteAnnouncer() {
  const { pathname } = useLocation();

  const firstRender = useRef(true);

  useEffect(() => {
    document.title = TITLES[pathname] ?? FALLBACK;

    // Move focus to <main> on navigation so AT announces the new page and focus
    // doesn't stay on the just-clicked link -- but not on the initial mount,
    // where the browser's default top-of-document focus is correct.
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    // Focus without scrolling (ScrollToTop already handles scroll position).
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [pathname]);

  return null;
}
