import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { ColdStartBanner } from "./components/ColdStartBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Nav } from "./components/Nav";
import { About } from "./pages/About";
import { ApiExplorer } from "./pages/ApiExplorer";
import { Compliance } from "./pages/Compliance";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { Methodology } from "./pages/Methodology";
import { NotFound } from "./pages/NotFound";
import { RouteDemo } from "./pages/RouteDemo";
import { Scheduler } from "./pages/Scheduler";
import { Settings } from "./pages/Settings";
import { SLAMonitor } from "./pages/SLAMonitor";

// Lazy-loaded so three.js / globe.gl stay out of the main bundle.
const CarbonGlobe = lazy(() => import("./pages/CarbonGlobe"));

export default function App() {
  return (
    <ErrorBoundary>
      <Nav />
      <ColdStartBanner />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/api-explorer" element={<ApiExplorer />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route
          path="/globe"
          element={
            <Suspense
              fallback={
                <div
                  style={{
                    height: "calc(100vh - 56px)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "#000",
                    color: "#94a3b8",
                  }}
                >
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
