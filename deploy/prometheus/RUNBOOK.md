# CarbonLens alert runbook

One page per alert in [`carbonlens.rules.yml`](carbonlens.rules.yml): what fired, how
to confirm, and how to fix. The fastest first step for any of these is `carbonlens
doctor` (or `carbonlens doctor --json` in CI) against the same deployment — it reports
API reachability, live-vs-estimated sources, and the marginal basis in one shot.

## CarbonMarginalUnmapped (warning)

**Means:** a measured-marginal credential (WattTime / Electricity Maps) is configured
but no zone is mapped, so no source was built and the marginal signal silently falls
back to heuristic. A misconfiguration, not a deliberate choice.

**Confirm:**
- `carbonlens doctor` shows the marginal line as `heuristic, but a marginal key IS configured`.
- `GET /api/v1/healthz/honesty` returns `marginal_configured_but_unmapped: true`.
- `carbon_marginal_unmapped` gauge is `1`.

**Fix:** set the matching zone map env and restart:
- WattTime: `CARBON_LENS_WATTTIME_ZONE_MAP` (e.g. `US-CAL-CISO:CAISO_NORTH,...`).
- Electricity Maps: `CARBON_LENS_ELECTRICITY_MAPS_ZONE_MAP`.

After restart the gauge returns to `0` and the basis becomes `measured` for mapped zones.

## CarbonGaugesAbsent (critical)

**Means:** no `carbon_intensity_gco2_kwh` series for 15m — the `/metrics` exporter is
down or every upstream source failed on the last scrape. Carbon-aware decisions are
flying blind until it recovers.

**Confirm:**
- `curl -s <api>/metrics | grep carbon_intensity_gco2_kwh` returns nothing.
- `carbonlens doctor` — the API line fails, or the data-sources line shows `0/N live`.

**Fix:**
- If the service is down, restart it and check logs.
- If the service is up but sources are failing, check provider API keys
  (`GET /health/providers`) and upstream status. CarbonLens degrades to estimates when
  a source is down; total absence usually means a key/network/exporter problem.

## CarbonNeverClean (info)

**Means:** every monitored grid zone has stayed above the clean tier for 24h. Often
genuine (grids really are dirty), but a stuck or stale feed looks identical.

**Confirm:**
- Spot-check one zone's `carbon_intensity_gco2_kwh` against the grid operator's own
  published number.
- Check `carbonlens doctor` data-sources line for a source stuck on errors.

**Fix:**
- If a feed is stale, treat it like `CarbonGaugesAbsent` (keys/upstream/exporter).
- If the grids are genuinely dirty, no action — consider widening the monitored zone
  set so you also track grids that do go clean.
