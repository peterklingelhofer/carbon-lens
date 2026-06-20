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

// What a "clean surplus" badge means. Shown wherever the oversupply heuristic
// surfaces (globe), so the claim stays honest about being inferred, not measured.
export const SURPLUS_TIP =
  "Renewables dominate generation, carbon is very low, and little or no fossil sits on the " +
  "margin - so extra demand is largely served by clean power that might otherwise be curtailed " +
  "(spilled). That makes it one of the best moments to run flexible jobs. Inferred from the live " +
  "mix, not measured curtailment or price data.";

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

// Tooltip copy for the alternatives/result tables shared by the API explorer and
// route demo. Kept here so both pages stay in sync.
export const EMISSIONS_TIP =
  "Carbon emitted per kilowatt-hour of electricity, in gCO₂/kWh - an intensity (emissions per " +
  "unit of power), not a total. Lower is cleaner.";

export const TABLE_RENEWABLE_TIP =
  "Share of the grid's power from renewables (wind, solar, hydro) right now. Low-carbon grids that " +
  "lean on nuclear (e.g. France, Sweden) can show a low renewable % while still emitting very " +
  "little CO₂ - and where no live fuel-mix feed is configured, this falls back to a weather " +
  "estimate that only sees solar and wind.";

export const GRID_ZONE_TIP =
  "The electricity grid (balancing authority) powering this region - e.g. US-NW-BPAT for Oregon, " +
  "SE-SE3 for southern Sweden. Carbon is measured at the grid, not the datacenter.";

export const SOURCE_TIP =
  "Where the reading came from: a live grid-operator feed (eia, entsoe, uk, aemo, …) or a " +
  "clearly-labelled estimate (e.g. the open_meteo weather model) when no live feed is configured " +
  "for that zone.";

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
