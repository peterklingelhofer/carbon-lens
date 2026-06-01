# CarbonLens

**Real-time carbon-intensity data API + compliance reporting for sustainable, carbon-aware cloud computing.**

*See the real carbon footprint behind your cloud — measure it, route around it, and report on it.*

![CarbonLens dashboard — live carbon intensity for cloud regions](docs/screenshots/hero-dashboard.png)

<sub>Live carbon-intensity dashboard. More screens: [API Explorer](docs/screenshots/03-api-explorer.png) · [Landing](docs/screenshots/01-landing.png) · [Carbon-aware routing](docs/screenshots/04-route.png) · [Compliance](docs/screenshots/06-compliance.png)</sub>

CarbonLens aggregates electricity-grid carbon data into a single developer-friendly API, behind one cascading interface. Six providers are live integrations against real grid-operator APIs (UK, EIA, AEMO, GridStatus, ENTSO-E, Electricity Maps); the rest are transparent heuristic estimators and a mock fallback, each labeled in the `source` field of every response so you always know what you're getting. On top of the data layer it adds carbon-aware routing, GHG-Protocol-structured compliance reporting, and Green SLA monitoring.

It's built for engineering and sustainability teams who want to **decarbonize their cloud workloads** — cutting the carbon footprint of compute with greener, lower-emission region choices, and backing it up with auditable ESG / CSRD emissions reporting. Think of it as the data layer for [green software](https://greensoftware.foundation/) and sustainable cloud operations.

**Keywords:** carbon-aware computing · cloud sustainability · carbon footprint · greenhouse-gas (GHG) emissions · decarbonization · green software · grid carbon intensity · Scope 2 & 3 reporting · CSRD / ESG · net-zero cloud.

> **Status:** This is a portfolio / demo project, not a production service. See [What's real vs. estimated vs. mock](#whats-real-vs-estimated-vs-mock) for an honest breakdown of which parts are live integrations and which are stubs.

## Why This Exists

Every major cloud provider claims "100% renewable energy." Most rely on **annual REC matching** — buying solar credits at noon to offset coal burned at midnight. Your 2 AM batch job in Virginia may run on a largely fossil grid while the provider settles up with offsets later.

**CarbonLens surfaces the underlying grid numbers.** Where a real grid-operator API exists for a region, it serves live gCO2/kWh from that source. Where one doesn't, it falls back to a labeled heuristic or mock value rather than pretending — so the data's provenance is always visible.

---

## Quick Start

**1. First-time setup** (installs deps, copies `.env`, builds the frontend):

```bash
git clone https://github.com/peterklingelhofer/carbonlens.git
cd carbonlens
make setup
```

**2. Run it** — one command, starts the API and the frontend with hot reload:

```bash
make dev
```

**3. Open it in your browser:**

| What to show | URL |
|--------------|-----|
| 🌍 **Live dashboard** — start here | **http://localhost:5173/dashboard** |
| Landing page | http://localhost:5173 |
| Interactive API Explorer | http://localhost:5173/api-explorer |
| Swagger API docs | http://localhost:8000/docs |

Runs out of the box with **no API keys** — 6 live government grid sources work key-free, and any region without a live source returns labeled fallback data. (Add keys to `.env` for US/EU live coverage; see [Adding Credentials](#adding-credentials).) Press `Ctrl+C` to stop.

> Already set up? Just `make dev` and open **http://localhost:5173/dashboard**.

### Try the API

```bash
# Get carbon intensity for AWS us-east-1 right now
curl http://localhost:8000/api/v1/carbon/aws/us-east-1

# Find the greenest region across all providers
curl -X POST http://localhost:8000/api/v1/route \
  -H "Content-Type: application/json" \
  -d '{"constraints": {"providers": ["aws", "gcp", "azure"], "carbon_weight": 1.0}}'

# Batch query multiple regions
curl -X POST http://localhost:8000/api/v1/carbon/batch \
  -H "Content-Type: application/json" \
  -d '[{"provider": "aws", "region": "us-east-1"}, {"provider": "gcp", "region": "europe-north1"}]'
```

### Code Examples

**Python:**
```python
import httpx

client = httpx.Client(base_url="https://api.carbonlens.dev", headers={"X-API-Key": "your_key"})

# Real-time carbon intensity
data = client.get("/api/v1/carbon/aws/us-east-1").json()
print(f"{data['carbon_intensity_gco2_kwh']} gCO2/kWh, {data['renewable_percentage']}% renewable")

# Find greenest region
route = client.post("/api/v1/route", json={
    "constraints": {"providers": ["aws", "gcp"], "carbon_weight": 1.0}
}).json()
print(f"Deploy to {route['recommended']['provider']} {route['recommended']['region']}")
```

**JavaScript/TypeScript:**
```typescript
const res = await fetch("https://api.carbonlens.dev/api/v1/carbon/aws/us-east-1", {
  headers: { "X-API-Key": "your_key" }
});
const { carbon_intensity_gco2_kwh, renewable_percentage } = await res.json();
```

---

## Products

### 1. Carbon Intensity API
Electricity-grid carbon data for 75+ cloud regions worldwide, behind one cascading interface — 6 live grid-operator integrations plus labeled heuristic and mock fallbacks.

| Feature | Free | Pro ($99/mo) | Enterprise |
|---------|------|-------------|------------|
| API queries/day | 100 | 50,000 | Unlimited |
| Data sources | 6 (no-key) | All 11 | All 11 + custom |
| Resolution | Hourly | 5-min | 5-min |
| Regions | 75+ | 75+ | 75+ + custom |
| Support | Community | Email | Dedicated |

### 2. Compliance Reporting
GHG-Protocol-structured Scope 2 + Scope 3 (Cat 1) emissions reporting for cloud workloads, aimed at CSRD / SEC Climate / California SB 253 disclosure workflows.

- **Scope 2** location-based emissions (real-time grid intensity × estimated energy)
- **Scope 3** Category 1 (purchased cloud services), estimated from grid intensity
- **GHG Protocol** report structure with documented methodology and data-quality summary
- **EU Taxonomy** eligibility flag (simplified screening, not a full DNSH assessment)
- **Usage input:** manual CSV upload, or live cloud-billing adapters — AWS Cost Explorer, GCP BigQuery billing export, Azure Cost Management (install the [`cloud` extra](#bringing-your-own-usage-data) + provide credentials)
- Export as JSON or CSV

> Scope: this generates a structured, defensible *first draft* of an emissions report. Market-based accounting (RECs/PPAs/residual mix), supplier-specific Scope 3 factors, utilization-aware energy modeling, and signed PDF output are **not** implemented — see the [roadmap](#whats-next). It is not a substitute for an assured CSRD report.

#### Bringing your own usage data

CarbonLens doesn't auto-detect where you run — you give it usage data, it maps service+region to energy (Cloud Carbon Footprint coefficients) and then to emissions via live grid intensity. Three ways in:

1. **Demo** — `POST /api/v1/compliance/usage/ingest` with `{"provider": "mock"}` (what the dashboard uses).
2. **Manual CSV** — `POST /api/v1/compliance/usage/upload-csv` (columns: `provider,region,service,resource_type,usage_quantity,usage_unit,period_start,period_end`).
3. **Live cloud billing** — pull real usage-by-region from your account:

```bash
uv sync --extra cloud   # installs boto3, google-cloud-bigquery, azure SDKs
```
```bash
# AWS Cost Explorer (needs ce:GetCostAndUsage permission)
curl -X POST localhost:8000/api/v1/compliance/usage/ingest -H 'Content-Type: application/json' -d '{
  "org_id": "acme", "provider": "aws",
  "period_start": "2026-05-01T00:00:00Z", "period_end": "2026-05-31T00:00:00Z",
  "credentials": {"aws_access_key_id": "...", "aws_secret_access_key": "..."}
}'
```
GCP needs a BigQuery billing export (`project_id`/`billing_dataset`/`billing_table`); Azure needs a service principal (`tenant_id`/`client_id`/`client_secret`/`subscription_id`).

> **Honesty note:** the three live adapters are implemented against the documented billing APIs and **unit-tested with mocked SDK responses** (parsing, pagination, unit-mapping, error handling), but they are **not yet verified against live cloud accounts**. Treat them as coded-to-spec, not battle-tested. Energy-from-usage is heuristic.

### 3. Carbon-Aware Routing
Route workloads to the greenest cloud region in real-time. Works with AWS, GCP, and Azure region sets.

### 4. Green SLA Monitoring (Beta)
Define carbon targets, run on-demand and background compliance checks against live grid data, and generate attestation-style summary reports. Note: the background monitor and all SLA/check/report state are currently **in-memory** (reset on restart, single-worker); the "attestation" format is a self-defined summary, not an assured third-party standard.

---

## Data Sources

CarbonLens cascades through 11 providers, using the highest-priority source that covers each grid zone. The **Type** column is the honest part: only `Live API` providers fetch and parse a real grid-operator response.

| # | Provider | Coverage | Type | Auth |
|---|----------|----------|------|------|
| 1 | UK Carbon Intensity | UK (18 zones) | **Live API** (renewable % estimated) | Free, no key |
| 2 | EIA (US DOE) | US (60+ balancing authorities) | **Live API** (intensity from fuel mix) | Free key |
| 3 | AEMO | Australia (5 states) | **Live API** (unofficial endpoint) | Free, no key |
| 4 | Grid India | India (5 regions) | Heuristic fallback | Free, no key |
| 5 | ONS Brazil | Brazil (5 regions) | Heuristic fallback | Free, no key |
| 6 | Eskom | South Africa | Heuristic (time-of-day model) | Free, no key |
| 7 | GridStatus.io | US ISOs (7) | **Live API** | Paid key |
| 8 | ENTSO-E | Europe (36+ countries) | **Live API** (IEC-62325 XML) | Free token |
| 9 | Open-Meteo | Worldwide (40+ zones) | **Estimate from weather** (not measured carbon) | Free, no key |
| 10 | Electricity Maps | Global (200+ zones) | **Live API** | Paid key |
| 11 | Mock (fallback) | All zones | Static demo data | None |

**Priority chain:** UK > EIA > AEMO > Grid India > ONS Brazil > Eskom > GridStatus > ENTSO-E > Open-Meteo > Electricity Maps > Mock

Every response includes a `source` field (e.g. `uk`, `eskom_heuristic`, `open_meteo`, `mock`) so callers can see exactly how a number was produced. The chain never errors out to the caller — if every real source fails for a zone, it falls through to labeled mock data rather than returning an error.

### What's real vs. estimated vs. mock

- **Live grid-operator APIs (6):** UK, EIA, AEMO, GridStatus, ENTSO-E, Electricity Maps. These fetch and parse real upstream responses. Three (GridStatus, Electricity Maps, plus EIA's higher tiers) need keys; ENTSO-E needs a free token.
- **Heuristic estimators (4):** Grid India and ONS Brazil attempt a live fetch but fall back to per-region constants with a time-of-day curve; Eskom always uses a time-of-day model; Open-Meteo derives a rough intensity from solar/wind weather data (it is **not** a carbon-measuring source). These are useful demo coverage, not authoritative data, and are tagged accordingly.
- **Mock (1):** static fixtures, clearly labeled, used only as a last-resort fallback so the API always returns *something*.

---

## API Reference

Interactive docs at `/docs` (Swagger) or `/redoc` (ReDoc) when the server is running.

### Carbon Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/carbon/{provider}/{region}` | GET | Real-time carbon intensity for a cloud region |
| `/api/v1/carbon/batch` | POST | Batch query multiple regions in one call |
| `/api/v1/regions` | GET | List all 75+ supported cloud regions |
| `/api/v1/regions?provider=aws` | GET | Filter regions by cloud provider |

### Routing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/route` | POST | Find the greenest region for your workload |
| `/api/v1/accounting/savings` | GET | Carbon savings report |

### Compliance

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/compliance/usage/ingest` | POST | Ingest cloud usage data |
| `/api/v1/compliance/calculate` | POST | Calculate Scope 2+3 emissions |
| `/api/v1/compliance/reports/generate` | POST | Generate CSRD-aligned report |
| `/api/v1/compliance/reports` | GET | List compliance reports |
| `/api/v1/compliance/reports/{id}` | GET | Get full report details |
| `/api/v1/compliance/reports/{id}/export` | GET | Export as JSON or CSV |

### Billing & Organizations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/billing/plans` | GET | Available plans (Free/Pro/Enterprise) |
| `/api/v1/billing/status` | GET | Current usage and tier |
| `/api/v1/orgs` | GET/POST | List or create organizations |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/ready` | GET | Readiness probe |
| `/health/providers` | GET | Data source configuration status |
| `/metrics` | GET | Prometheus metrics |
| `/ws/carbon` | WS | Real-time carbon intensity WebSocket stream |
| `/docs` | GET | Swagger UI |

---

## Adding Credentials

CarbonLens works out of the box with 6 no-key providers. Add API keys for more real-time government data:

```bash
# .env
CARBON_MESH_EIA_API_KEY=your_eia_key           # US grid (free: eia.gov/opendata)
CARBON_MESH_GRID_STATUS_API_KEY=your_key        # US ISOs (free: gridstatus.io)
CARBON_MESH_ENTSOE_TOKEN=your_token             # Europe (free: transparency.entsoe.eu)
CARBON_MESH_ELECTRICITY_MAPS_API_KEY=your_key   # Global (paid: electricitymaps.com)
```

Verify: `curl http://localhost:8000/health/providers`

---

## Cloud Region Coverage

75+ cloud regions across three major providers:

- **AWS** — 26 regions
- **GCP** — 37 regions
- **Azure** — 35 regions

Each region is mapped to a physical electricity grid zone in `data/region_grid_map.yaml`.

---

## Architecture

```
src/carbon_mesh/
  api/              FastAPI routes + dependency injection + WebSocket
  auth/             API key generation, hashing, validation
  billing/          Usage tracking, tier limits, Stripe integration
  carbon_sources/   11 pluggable data providers (Protocol-based)
  compliance/       CSRD/SEC/SB-253 emissions reporting
  engine/           Carbon-aware routing engine + scorer + cache
  grid/             Cloud region <-> electricity grid zone mapper
  models/           Pydantic domain models
  accounting/       Per-request carbon tracking + savings reports
  db/               SQLAlchemy async models + Alembic migrations
  orgs/             Multi-tenant organization management
  cli/              Typer CLI (carbonlens route, intensity, regions)
  config.py         Environment-based config with validation
  main.py           FastAPI app, middleware, lifespan

web/                Vite + React 19 + TypeScript frontend
  src/pages/        Landing, API Explorer, Dashboard, Compliance, Plans, Settings, Orgs
  src/api/          Typed API client + WebSocket

terraform/          Terraform data source for green routing
data/               region_grid_map.yaml (75+ regions -> grid zones)
alembic/            Database migrations
tests/              205 tests
```

```
                ┌──────────────┐
                │   Frontend   │  Vercel / Netlify
                │  (React/Vite)│
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │   API Server │  Fly.io / Render / Docker
                │   (FastAPI)  │
                └──┬───┬───┬───┘
                   │   │   │
          ┌────────┘   │   └────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Postgres │ │  Carbon  │ │  Cloud   │
    │  (state) │ │  Data    │ │ Provider │
    └──────────┘ │ Sources  │ │  APIs    │
                 └──────────┘ └──────────┘
                 EIA, ENTSO-E,  AWS, GCP,
                 UK, AEMO, ...  Azure
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Data Sources** | | |
| `CARBON_MESH_CARBON_SOURCE` | `hybrid` | Mode: `hybrid`, `mock`, `eia`, etc. |
| `CARBON_MESH_EIA_API_KEY` | | EIA API key |
| `CARBON_MESH_GRID_STATUS_API_KEY` | | GridStatus API key |
| `CARBON_MESH_ENTSOE_TOKEN` | | ENTSO-E token |
| `CARBON_MESH_ELECTRICITY_MAPS_API_KEY` | | Electricity Maps key |
| `CARBON_MESH_CACHE_TTL_SECONDS` | `300` | Cache TTL for grid data |
| **Server** | | |
| `CARBON_MESH_HOST` | `0.0.0.0` | Bind address |
| `CARBON_MESH_PORT` | `8000` | Bind port |
| `CARBON_MESH_CORS_ORIGINS` | `["http://localhost:5173"]` | CORS origins |
| **Database** | | |
| `CARBON_MESH_USE_DATABASE` | `false` | Enable Postgres |
| `CARBON_MESH_DATABASE_URL` | `postgresql+asyncpg://...` | Postgres URL |
| `CARBON_MESH_AUTO_MIGRATE` | `false` | Auto-run migrations |
| **Auth** | | |
| `CARBON_MESH_API_KEY_REQUIRED` | `false` | Require API key |
| `CARBON_MESH_ADMIN_SECRET` | | Admin endpoint secret |
| **Limits** | | |
| `CARBON_MESH_RATE_LIMIT_DEFAULT` | `100/minute` | Default rate limit |
| `CARBON_MESH_RATE_LIMIT_ROUTE` | `30/minute` | Route endpoint limit |
| **Observability** | | |
| `CARBON_MESH_LOG_FORMAT` | `text` | `text` or `json` |
| `CARBON_MESH_LOG_LEVEL` | `INFO` | Log level |

---

## Deployment

| Platform | How | Config |
|----------|-----|--------|
| **Docker** | `make up` | `Dockerfile`, `docker-compose.yml` |
| **Render** | New Blueprint Instance | `render.yaml` |
| **Fly.io** | `fly launch --copy-config --yes` | `fly.toml` |
| **GHCR images** | published by CI on merge to `main` | `.github/workflows/ci.yml` |
| **Vercel** (frontend) | Connect repo, root = `web/` | `web/vercel.json` |
| **Kubernetes** | illustrative Helm chart (see `k8s/README.md`) | `k8s/` |

---

## Development

```bash
make help       # show all commands
make setup      # install deps + copy .env + build frontend
make dev        # API + frontend with hot reload
make test       # 205 tests
make lint       # ruff + tsc
make fix        # auto-fix lint
make migrate    # run Alembic migrations
make up         # docker compose
make down       # stop everything
```

---

## The Vision

CarbonLens demonstrates the **carbon data layer** that carbon-aware infrastructure decisions
would be built on: a single cascading API over multiple grid sources, plus the routing,
reporting, and monitoring tooling that sits on top of it.

**What's built (and real):**
- Cascading carbon intensity API with **6 live grid-operator integrations** + labeled heuristic/mock fallbacks
- 75+ cloud regions mapped to electricity grid zones
- Carbon-aware routing engine (find the greenest region) with stale-while-revalidate caching
- GHG-Protocol-structured Scope 2 + Scope 3 (Cat 1) compliance reporting (location-based)
- Green SLA check engine with on-demand + background monitoring (in-memory)
- Live cloud-billing ingestion adapters (AWS/GCP/Azure) — coded-to-spec + mock-tested (not live-verified)
- Multi-tenant orgs with hashed API keys and Stripe billing integration
- React 19 dashboard with a live WebSocket carbon feed
- 205 tests, multi-stage Docker build, Alembic migrations

**What's next (not yet real):**
- Market-based Scope 2 accounting (RECs/PPAs/residual mix) and supplier-specific Scope 3 factors
- Utilization-aware energy modeling (current model assumes flat draw per vCPU-hour)
- Signed PDF compliance reports and a recognized attestation standard
- Durable (Postgres-backed) SLA monitoring that starts at boot and survives restarts
- Validating the cloud-billing adapters against live accounts; historical/forecast carbon endpoints

## Companion project: carbon-aware CI/CD

Want to *act* on this data in your pipelines? **[carbon-aware-dispatcher](https://github.com/peterklingelhofer/carbon-aware-dispatcher)** is a sibling project — a single GitHub Action that runs your CI/CD only when the energy grid is clean:

```yaml
- uses: peterklingelhofer/carbon-aware-dispatcher@v1
  id: carbon
  with:
    grid_zones: 'auto:green'   # auto-detect region, or pick the cleanest free zone
- if: steps.carbon.outputs.grid_clean == 'true'
  run: ./build.sh             # only runs when the grid is green
```

CarbonLens is the **data + reporting layer** (measure, route, report); the dispatcher is the **enforcement layer** for deferrable jobs (CI, ML training, batch). Same carbon-aware mission, different point in the workflow.

## License

MIT
