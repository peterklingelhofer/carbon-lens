import type { CSSProperties } from "react";

// Shared explanation of the "live" vs "estimated" data-quality labels, reused
// wherever those badges/counts appear (globe, dashboard, compliance) so the
// clarity is consistent across the site.

// Why a higher renewable % doesn't always mean lower carbon - nuclear is clean
// but isn't counted as renewable. Shown wherever renewable % sits next to carbon
// intensity (scheduler, globe) so the apparent mismatch is explained.
export const RENEWABLE_TIP =
  "A higher renewable % isn't always lower carbon. It counts wind, solar and hydro but not " +
  "nuclear, so a clean nuclear grid (e.g. France, Ontario) can show a modest renewable % yet " +
  "very low carbon. For how clean a region is, carbon intensity (gCO₂/kWh) is the better measure.";

// Why marginal intensity is the number that matters for shifting load. Shown
// wherever marginal sits next to the average (dashboard, globe) so the gap is
// explained consistently.
export const MARGINAL_TIP =
  "Estimated emissions of an extra kWh of demand right now, set by the price-setting generator " +
  "(usually the flexible gas peaker). That's what actually changes when you shift load - not the " +
  "average. So a grid can look clean on average yet still meet extra demand with fossil fuel. A " +
  "heuristic from the fuel mix, not measured marginal data.";

// Plain-string form - for native attributes that need a string (e.g. title=).
export const DATA_QUALITY_TIP =
  "Live = measured from the grid operator's real-time feed (EIA, ENTSO-E, UK, AEMO). " +
  "Estimated = no live feed for that zone, so it's modelled from weather or a regional " +
  "grid-mix heuristic: a reasonable approximation, not a measurement.";

// Rich form - same copy, but the two labels are rounded colour pills (green =
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
