import { Route, Routes, useLocation } from "react-router-dom";
import { ColdStartBanner } from "./components/ColdStartBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Nav } from "./components/Nav";
import { RouteAnnouncer } from "./components/RouteAnnouncer";
import { ScrollToTop } from "./components/ScrollToTop";
import { NotFound } from "./pages/NotFound";
import { ROUTES } from "./routes";

export default function App() {
  return (
    <ErrorBoundary>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <ScrollToTop />
      <RouteAnnouncer />
      {/* The nav's own `position: sticky` resolves against its containing block,
          so once it's wrapped in <header> the header must carry the sticky (a
          nav-height box can't keep its child pinned past its own bottom). */}
      <header style={{ position: "sticky", top: 0, zIndex: 20 }}>
        <Nav />
      </header>
      <ColdStartBanner />
      {/* tabIndex=-1 makes <main> a programmatic focus target for the skip link
          and post-navigation focus move, without putting it in the tab order. */}
      <main id="main" tabIndex={-1}>
        <RoutedContent />
      </main>
    </ErrorBoundary>
  );
}

// Page content sits behind its own error boundary, keyed on the path so a crash
// in one page leaves the Nav intact and clears itself when the user navigates
// elsewhere; the outer boundary only trips for app-shell (Nav) failures.
function RoutedContent() {
  const location = useLocation();
  return (
    <ErrorBoundary key={location.pathname}>
      <Routes>
        {ROUTES.flatMap((r) =>
          [r.path, ...(r.aliases ?? [])].map((path) => (
            <Route key={path} path={path} element={r.element} />
          )),
        )}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ErrorBoundary>
  );
}
