import { lazy, type ReactNode, Suspense } from "react";
import { About } from "./pages/About";
import { ApiExplorer } from "./pages/ApiExplorer";
import { CleanCompute } from "./pages/CleanCompute";
import { Compliance } from "./pages/Compliance";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { Methodology } from "./pages/Methodology";
import { RouteDemo } from "./pages/RouteDemo";
import { Scheduler } from "./pages/Scheduler";
import { Settings } from "./pages/Settings";
import { SLAMonitor } from "./pages/SLAMonitor";

// Lazy-loaded so three.js / globe.gl stay out of the main bundle.
const CarbonGlobe = lazy(() => import("./pages/CarbonGlobe"));

const globe = (
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
);

export interface AppRoute {
  /** Canonical path. Nav links here and the router matches it exactly. */
  path: string;
  /** Nav label. Plain words over jargon: someone who doesn't work in cloud
   *  infrastructure should be able to guess what the page does. */
  label: string;
  /** Document title, set on navigation (SPA routing never reloads the page). */
  title: string;
  element: ReactNode;
  /** Older paths kept working, so links already in the wild don't 404. */
  aliases?: string[];
  /** NavLink needs `end` on "/" or it matches every route. */
  end?: boolean;
}

// The one place routes, nav labels and page titles are defined; App, Nav and
// RouteAnnouncer all read from here so the three can't drift apart.
export const ROUTES: AppRoute[] = [
  {
    path: "/",
    label: "Globe",
    title: "Carbon Lens - live carbon intensity for cloud regions",
    element: globe,
    aliases: ["/globe"],
    end: true,
  },
  {
    path: "/intro",
    label: "Intro",
    title: "Intro - Carbon Lens",
    element: <Landing />,
  },
  {
    path: "/regions",
    label: "All regions",
    title: "All regions - Carbon Lens",
    element: <Dashboard />,
    aliases: ["/dashboard"],
  },
  {
    path: "/find-a-region",
    label: "Find a region",
    title: "Find a region - Carbon Lens",
    element: <RouteDemo />,
    aliases: ["/route"],
  },
  {
    path: "/best-time",
    label: "Best time",
    title: "Best time to run - Carbon Lens",
    element: <Scheduler />,
    aliases: ["/scheduler"],
  },
  {
    path: "/report",
    label: "Report",
    title: "Emissions reporting - Carbon Lens",
    element: <Compliance />,
    aliases: ["/compliance"],
  },
  {
    path: "/targets",
    label: "Targets",
    title: "Carbon targets - Carbon Lens",
    element: <SLAMonitor />,
    aliases: ["/sla"],
  },
  {
    path: "/trends",
    label: "Trends",
    title: "State of clean compute - Carbon Lens",
    element: <CleanCompute />,
    aliases: ["/clean-compute"],
  },
  {
    path: "/api",
    label: "API",
    title: "API explorer - Carbon Lens",
    element: <ApiExplorer />,
    aliases: ["/api-explorer"],
  },
  {
    path: "/methodology",
    label: "Methodology",
    title: "Methodology - Carbon Lens",
    element: <Methodology />,
  },
  {
    path: "/status",
    label: "Status",
    title: "Status - Carbon Lens",
    element: <Settings />,
    aliases: ["/settings"],
  },
  {
    path: "/about",
    label: "About",
    title: "About - Carbon Lens",
    element: <About />,
  },
];

/** Document titles by path, including aliases so an old link still announces
 *  the right page name. */
export const TITLES: Record<string, string> = Object.fromEntries(
  ROUTES.flatMap((r) => [r.path, ...(r.aliases ?? [])].map((p) => [p, r.title])),
);
