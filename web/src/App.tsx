import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { Nav } from "./components/Nav";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ColdStartBanner } from "./components/ColdStartBanner";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { RouteDemo } from "./pages/RouteDemo";
import { Settings } from "./pages/Settings";
import { About } from "./pages/About";
import { Methodology } from "./pages/Methodology";
import { Compliance } from "./pages/Compliance";
import { ApiExplorer } from "./pages/ApiExplorer";
import { Scheduler } from "./pages/Scheduler";
import { SLAMonitor } from "./pages/SLAMonitor";
import { NotFound } from "./pages/NotFound";

// Lazy-loaded so three.js / globe.gl stay out of the main bundle.
const CarbonGlobe = lazy(() => import("./pages/CarbonGlobe"));

export default function App() {
  return (
    <ErrorBoundary>
      <ColdStartBanner />
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/api-explorer" element={<ApiExplorer />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route
          path="/globe"
          element={
            <Suspense
              fallback={
                <div style={{ height: "calc(100vh - 56px)", display: "flex", alignItems: "center", justifyContent: "center", background: "#000", color: "#94a3b8" }}>
                  Loading globe…
                </div>
              }
            >
              <CarbonGlobe />
            </Suspense>
          }
        />
        <Route path="/route" element={<RouteDemo />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/sla" element={<SLAMonitor />} />
        <Route path="/scheduler" element={<Scheduler />} />
        <Route path="/about" element={<About />} />
        <Route path="/methodology" element={<Methodology />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ErrorBoundary>
  );
}
