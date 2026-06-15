# CarbonLens — how it works, and why it's built this way

A short tour of the engineering decisions behind CarbonLens. For the component map
see [ARCHITECTURE.md](../ARCHITECTURE.md); to build it see
[CONTRIBUTING.md](../CONTRIBUTING.md).

## The problem

Electricity grids are dramatically cleaner at some times and places than others —
hydro-heavy Oregon vs coal-heavy elsewhere, midday solar vs an evening gas peak.
Cloud workloads are often flexible in *where* and *when* they run. So the question
is simple: **make it trivial to see grid carbon and act on it — and keep it free.**

Most tools in this space sell *data*. CarbonLens optimizes for *observability and
action*: see it (dashboard, globe, Prometheus, badges, embeds), decide (forecast,
heatmap, comparison, "cleaner than usual"), and act (routing, scheduling, a
carbon-aware CLI, a one-call signal endpoint).

## Decisions worth calling out

**Honesty about data quality is a feature.** Every reading is tagged live /
estimated / mock, and the UI never hides an estimate behind a real one. Heuristics
(marginal intensity, the time-of-day forecast, weather estimates) are labelled as
such everywhere. The globe colours by *carbon intensity* — which counts nuclear and
hydro — rather than renewable %, because the rigorous "how clean" answer matters
more than a marketing number. When I added a forecast uncertainty band, I made it an
explicitly *illustrative* band that widens with the horizon — not a fake statistical
confidence interval — to stay consistent with that ethos.

**Fixed-cost public data.** Viewer traffic never hits upstream provider APIs. A
scheduled GitHub Action builds a snapshot (and a rolling history archive) and
publishes it to a CDN; the app reads that. Quota cost is `O(zones × cadence)`, not
`O(users)` — which is what makes a genuinely free public demo possible. Resilience
touches: carry-forward across brief upstream gaps, and a stale-while-revalidate
cache.

**The spec and the client can't drift.** FastAPI generates the OpenAPI schema; it's
exported to a checked-in `openapi.json` and a generated TypeScript client, and CI
fails if either falls out of sync with the routes. The contract stays honest by
construction.

**Pluggable persistence, free durability.** SLA storage sits behind a repository
protocol with in-memory and Postgres backends, chosen per request. Durable
*scheduled* checking on a scale-to-zero host doesn't need a paid always-on worker —
a GitHub Actions cron POSTs to an admin endpoint. A startup seeder keeps a demo SLA
present (self-healing after a reset or redeploy).

**Loose coupling over merged code.** The companion carbon-aware-dispatcher stays a
separate project; they interlink through a stable contract — the `/carbon/signal`
traffic-light endpoint (`green/yellow/red` + the next cleaner window) — not shared
code. One primitive anyone can poll.

**Free where it counts.** The day/night terminator on the globe is pure astronomy
from the clock — no weather API — and it *explains* the product (solar-heavy grids
clean up on the lit side). The non-EU forecast upgrade reuses free Open-Meteo data.

## Quality

`pyright` + `ruff` on the backend, `biome` + `tsc` on the frontend, ~250 backend
tests and ~50 frontend tests (component tests via Testing Library + jsdom, including
the globe's presentational pieces extracted into testable modules). Parser fixture
tests catch upstream format drift before a zone silently goes dark. CI also guards
the OpenAPI/client drift and runs the snapshot job on a schedule.

## Deliberately not done

- **Global consumption-based intensity** — needs paid cross-border flow data;
  consumption tracing is EU-only (free ENTSO-E). Not faked.
- **Measured marginal emissions** — the marginal figure is a labelled fuel-mix
  heuristic, not a dispatch model or paid marginal feed.
- **A stateful public demo** — the live demo is intentionally stateless (no signup,
  clean slate); durable persistence is available for self-hosters who want it.

## What's next

Once the history archive has accumulated, the "cleaner than usual" baseline gets
sharper. Beyond that: more cloud providers / on-prem coverage, and (if a data
budget ever appears) real marginal emissions.
