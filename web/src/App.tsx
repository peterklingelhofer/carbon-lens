import { Routes, Route } from "react-router-dom";
import { Nav } from "./components/Nav";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { RouteDemo } from "./pages/RouteDemo";
import { Settings } from "./pages/Settings";
import { Plans } from "./pages/Plans";
import { Organizations } from "./pages/Organizations";
import { Compliance } from "./pages/Compliance";
import { ApiExplorer } from "./pages/ApiExplorer";
import { Scheduler } from "./pages/Scheduler";
import { SLAMonitor } from "./pages/SLAMonitor";
import { NotFound } from "./pages/NotFound";

export default function App() {
  return (
    <ErrorBoundary>
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/api-explorer" element={<ApiExplorer />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/route" element={<RouteDemo />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/sla" element={<SLAMonitor />} />
        <Route path="/scheduler" element={<Scheduler />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/orgs" element={<Organizations />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ErrorBoundary>
  );
}
