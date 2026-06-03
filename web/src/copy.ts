// Shared explanation of the "live" vs "estimated" data-quality labels, reused
// wherever those badges/counts appear (globe, dashboard, compliance) so the
// clarity is consistent across the site.
export const DATA_QUALITY_TIP =
  "Live = read straight from the grid operator's own real-time feed (EIA, ENTSO-E, " +
  "UK Carbon Intensity, AEMO, GridStatus…). It's a measured value — the most accurate " +
  "we have. Estimated = no live feed is available for that zone right now, so the value " +
  "is inferred and clearly labelled: either from a weather model (current solar irradiance " +
  "and wind speed via Open-Meteo) or a regional heuristic (typical local grid mix by time " +
  "of day). It's a reasonable approximation, not a direct measurement.";
