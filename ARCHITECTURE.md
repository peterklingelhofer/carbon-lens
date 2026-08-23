# Architecture

How CarbonLens is put together, and the design decisions behind it. For setup and
contribution mechanics, see [CONTRIBUTING.md](CONTRIBUTING.md).

## The shape of it

```
                 ┌──────────────────────────────────────────────┐
  Grid operators │  EIA · ENTSO-E · UK · OpenElectricity/AEMO ·  │
  (live APIs)    │  IESO/AESO · Taipower · GridStatus · EM       │
                 └───────────────────┬──────────────────────────┘
                                     │  (per-fuel mix -> emission factors)
                          ┌──────────▼───────────┐
                          │  HybridCarbonSource  │  cascade: first source that
                          │  (priority cascade)  │  covers a zone wins; falls
                          └──────────┬───────────┘  through to labeled mock
        scheduled GitHub Action      │
        scripts/build_snapshot.py    │ get_carbon_intensity[_batch]
                  │                   │
                  ▼                   ▼
         snapshot.json + history.json (published to the `data` branch / CDN)
                  │                   │
   FastAPI reads ─┘                   └─ SnapshotBackedSource (one cached fetch,
   (frontend reads snapshot directly)    replacing N live calls per request)
                  │
   ┌──────────────┼───────────────────────────────────────────────┐
   │  FastAPI app (src/carbonlens)                                  │
   │  /carbon (now/forecast/history/zone/batch) · /route · /scheduler│
   │  /compliance · /sla · /metrics · /badge · /ws/carbon            │
   └──────────────┬───────────────────────────────────────────────┘
                  ▼
   React 19 + Vite SPA (web/) · CLI (carbonlens) · Prometheus/Grafana · badges
```

## Carbon data: the cascade

[`HybridCarbonSource`](src/carbonlens/carbon_sources/hybrid.py) holds an ordered
provider chain. For a zone it tries each source that declares coverage and returns
the first success; if a live provider fails it logs a warning and moves on, and if
nothing covers the zone it falls through to labeled **mock** data (logged at INFO so
a zone going dark is visible in snapshot-builder logs). Priority, roughly:

> UK -> EIA -> OpenElectricity/AEMO -> IESO/AESO -> Taipower -> Grid India -> ONS Brazil
> -> Eskom -> GridStatus -> ENTSO-E -> Open-Meteo -> Electricity Maps -> Mock

Most providers report a **fuel mix** (MW per fuel); [`emission_factors.py`](src/carbonlens/carbon_sources/emission_factors.py)
turns that into intensity (`calculate_carbon_intensity`), renewable %, a marginal
estimate (`calculate_marginal_intensity`, the price-setting fuel, a labeled
heuristic), and the per-fuel `power_breakdown`. XML feeds (ENTSO-E, IESO) parse via
`defusedxml`.

### Data-quality philosophy

Every reading is tagged **live / estimated / mock** and the UI never hides an
estimate behind a real one. Heuristics (marginal intensity, the time-of-day
forecast, weather-based Open-Meteo) are always labeled as such. This labeling is a
feature: it's why the globe colors by carbon intensity (which
counts nuclear/hydro) rather than renewable %.

## The snapshot: fixed-cost public data

User traffic never hits upstream provider APIs. A scheduled GitHub Action runs
[`build_snapshot.py`](scripts/build_snapshot.py), which fans out across all zones
once and publishes `snapshot.json` (current) and `history.json` (a rolling
per-region archive) to a `data` branch / CDN. Quota cost is `O(zones × cadence)`
regardless of user count. The frontend reads the snapshot directly; the API reads it via
[`SnapshotBackedSource`](src/carbonlens/carbon_sources/snapshot_source.py) (one
cached fetch instead of dozens of live calls per request). Two resilience touches:
**carry-forward** (a brief upstream gap keeps the last *live* reading rather than
dropping to an estimate) and an in-memory **stale-while-revalidate cache**.

## Consumption, forecast, history

- **Consumption-based intensity** (`flow_tracing.py`): for the interconnected
  European grid, solves the import/export network (Tranberg et al.) so a zone's
  consumption carries the intensity of its real import mix.
- **Forecast** (`/carbon/forecast`, `entsoe_forecast.py` + `scheduler/engine.py`):
  EU zones use ENTSO-E's real day-ahead wind/solar/load forecast; elsewhere a
  local-solar-time-of-day model. Each point names its `method`.
- **History** (`/carbon/history`): served from the published rolling archive, so
  it accumulates over time without a database.

## Routing & scheduling

- **Routing** ([`engine/router.py`](src/carbonlens/engine/router.py)) ranks
  candidate regions by a carbon/cost weighted score; default favors lowest carbon
  intensity. Greenest = lowest gCO₂/kWh, so a high renewable % alone doesn't win.
- **Scheduling** ([`scheduler/engine.py`](src/carbonlens/scheduler/engine.py))
  projects each region across a delay window and picks the cleanest slot; the
  `carbonlens run` CLI uses the same forecast to defer a job to a green window.

## SLA monitoring: pluggable persistence

SLA definitions, checks, and reports go through an
[`SLARepository`](src/carbonlens/sla/repository.py) with two backends behind one
protocol: `InMemorySLARepository` (keyless demo, tests) and `DBSLARepository`
(Postgres, durable). `get_sla_repository` picks per request based on
`CARBON_LENS_USE_DATABASE`. Durable *scheduled* checking on a scale-to-zero host
uses a GitHub Actions cron hitting the admin-only `/sla/monitor/run`, rather than
an always-on worker. A startup seeder keeps a demo SLA present (self-healing).

## API surface & contracts

FastAPI generates the OpenAPI schema; it's exported to a checked-in
[`openapi.json`](openapi.json) (`make openapi`) and a TypeScript client
[`web/src/api/schema.ts`](web/src/api/schema.ts) (`npm run gen:api`). CI fails if
either drifts from the committed copy, so the spec and client can't fall out of
sync with the routes. Observability extras: Prometheus carbon gauges on `/metrics`
(+ a Grafana dashboard) and embeddable SVG status badges at `/badge/...`.

## Layout

```
src/carbonlens/
  carbon_sources/   provider integrations + hybrid cascade + emission factors
  engine/           routing, scoring, intensity cache
  scheduler/        carbon-aware window selection + forecast projection
  sla/              SLA engine, repository (in-memory/DB), monitor, seed
  compliance/       GHG-Protocol Scope 2/3 reporting + billing adapters
  api/              FastAPI deps, routes, metrics, badge, websocket
  grid/             region -> grid-zone mapper
  models/           pydantic domain models
scripts/build_snapshot.py   the scheduled snapshot/history builder
web/                React 19 + Vite SPA
```
