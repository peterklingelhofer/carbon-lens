import type { CSSProperties } from "react";

// Shared explanation of the "live" vs "estimated" data-quality labels, reused
// wherever those badges/counts appear (globe, dashboard, compliance) so the
// clarity is consistent across the site.

// Plain-string form — for native attributes that need a string (e.g. title=).
export const DATA_QUALITY_TIP =
  "Live = measured from the grid operator's real-time feed (EIA, ENTSO-E, UK, AEMO). " +
  "Estimated = no live feed for that zone, so it's modelled from weather or a regional " +
  "grid-mix heuristic: a reasonable approximation, not a measurement.";

// Rich form — same copy, but the two labels are rounded colour pills (green =
// live, amber = estimated) using the exact badge/dot colours, with dark text so
// they stay legible in light and dark mode. Split onto their own lines so the
// tip scans at a glance instead of reading as one block. For InfoTip content.
const pill = (bg: string, fg: string): CSSProperties => ({
  display: "inline-block",
  padding: "0 6px",
  borderRadius: 5,
  fontWeight: 700,
  background: bg,
  color: fg,
});

export const DATA_QUALITY_TIP_RICH = (
  <>
    <span style={pill("#4ade80", "#052e16")}>Live</span> = measured from the grid operator's
    real-time feed (EIA, ENTSO-E, UK, AEMO).
    <br />
    <br />
    <span style={pill("#fbbf24", "#422006")}>Estimated</span> = no live feed for that zone, so it's
    modelled from weather or a regional grid-mix heuristic: a reasonable approximation, not a
    measurement.
  </>
);
