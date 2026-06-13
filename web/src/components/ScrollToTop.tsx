import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// Single-page route changes don't reset the scroll position, so navigating from
// a long page (e.g. the dashboard) would land the user mid-page on the next one.
// Reset to the top whenever the path changes. In-page hash links keep their own
// anchor behaviour, so we only react to pathname (not hash) changes.
export function ScrollToTop() {
  const { pathname } = useLocation();
  // biome-ignore lint/correctness/useExhaustiveDependencies: pathname is the trigger, not read in the body -- the effect must re-run on each navigation to reset scroll.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
