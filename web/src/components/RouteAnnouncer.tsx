import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { TITLES } from "../routes";

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
    // doesn't stay on the just-clicked link, but not on the initial mount,
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
