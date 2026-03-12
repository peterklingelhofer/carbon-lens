# Carbon Mesh

**The cloud runs on coal at night. We fix that.**

Carbon Mesh is a carbon-aware compute platform that guarantees your workloads run on genuinely clean energy — not offset accounting tricks, not annual matching spreadsheets, but actual renewable electrons flowing through the grid at the moment your code executes.

We monitor real-time electricity grid data from 11 data sources across 90+ grid zones worldwide, and route your compute to whichever region is physically running on the cleanest energy right now.

## Why This Exists

### The "100% Renewable" Lie

Every major cloud provider claims to be "100% powered by renewable energy." They are not. Here is what they actually do:

**Annual Matching** — If a data center consumes 100 MWh of electricity in a year, the provider purchases 100 MWh of renewable energy certificates (RECs) or signs power purchase agreements (PPAs) for that amount. On an annual spreadsheet, their carbon footprint nets to zero.

But data centers run 24/7. When the sun sets and the wind stops, your servers are still drawing power from the local grid. If that grid burns coal or natural gas at 2 AM, your code is running on fossil fuels. The cloud provider simply "offsets" that midnight pollution with surplus solar credits they purchased from a farm in a different state at noon.

**This is not clean computing. This is carbon accounting.**

### What the Big Three Actually Do

| Provider | Claim | Reality |
|----------|-------|---------|
| **AWS** | "100% renewable matched" (2023) | Annual matching via RECs. World's largest corporate renewable energy buyer — but the vast majority of infrastructure sits in "Data Center Alley" in Northern Virginia, a grid that runs 60-85% on fossil fuels at any given hour. |
| **Google Cloud** | "24/7 Carbon-Free Energy by 2030" | The most transparent of the three. Currently ~64% CFE globally. Some regions (Finland, Iowa) exceed 90%. Others (Singapore, Virginia) are below 30%. Google publishes hourly data — they know the gap is real. |
| **Microsoft Azure** | "100/100/0 by 2030" | 100% of electricity, 100% of the time, 0 carbon. Ambitious target, but currently not met. Investing in small modular nuclear reactors as a long-term solution. |

### What Carbon Mesh Does Differently

Instead of buying offsets after the fact, we **move the compute to where the energy is already clean.**

```
Traditional cloud:  Pick region -> Run job -> Buy carbon offsets later
Carbon Mesh:        Check grid data -> Find cleanest region NOW -> Run job there
```

We call this **real-time carbon arbitrage** — chasing the sun and wind across the globe to keep your workloads on genuinely renewable infrastructure.

---

## Quick Start

### Option 1: Local Development (30 seconds)

```bash
git clone https://github.com/your-org/carbon-mesh-control-plane.git
cd carbon-mesh-control-plane
make setup    # installs deps, copies .env, builds frontend
make dev      # starts API on :8000 + frontend on :5173
```

### Option 2: Docker (one command)

```bash
cp .env.example .env
# Add API keys (see "Adding Credentials" below)
make up
# API: http://localhost:8000  |  Web: http://localhost:5173  |  Docs: http://localhost:8000/docs
```

### Option 3: One-Click Cloud Deploy

| Platform | How | Config File |
|----------|-----|-------------|
| **Render** | New Blueprint Instance -> point to repo | `render.yaml` |
| **Fly.io** | `fly launch --copy-config --yes` | `fly.toml` |
| **Railway** | Connect repo at railway.app | `railway.toml` |
| **Heroku** | `git push heroku main` | `Procfile` |
| **Vercel** (frontend) | Connect repo, root = `web/` | `web/vercel.json` |
| **Netlify** (frontend) | Connect repo, base = `web/` | `web/netlify.toml` |

> After deploying, verify: `curl https://your-app.fly.dev/health/providers`

---

## Adding Credentials

Carbon Mesh works out of the box with 6 no-key providers. Add API keys for 4 more to unlock real-time government grid data:

### Step 1: Get Free API Keys (5 minutes total)

| # | Provider | Coverage | Sign Up | Time |
|---|----------|----------|---------|------|
| 1 | **EIA** | US grid (real-time hourly) | [eia.gov/opendata](https://www.eia.gov/opendata/) | 1 min |
| 2 | **GridStatus** | US ISOs (CAISO, ERCOT, PJM, etc.) | [gridstatus.io](https://www.gridstatus.io/) | 1 min |
| 3 | **ENTSO-E** | Europe (35 countries, hourly) | [transparency.entsoe.eu](https://transparency.entsoe.eu/) | 2 min |
| 4 | **Electricity Maps** | Global (200+ zones, paid) | [electricitymaps.com](https://api-portal.electricitymaps.com/) | Optional |

### Step 2: Add Keys to Your Environment

**Local development** — edit `.env`:
```bash
# .env (copy from .env.example)
CARBON_MESH_EIA_API_KEY=your_eia_key_here
CARBON_MESH_GRID_STATUS_API_KEY=your_gridstatus_key_here
CARBON_MESH_ENTSOE_TOKEN=your_entsoe_token_here
CARBON_MESH_ELECTRICITY_MAPS_API_KEY=your_emaps_key_here   # optional, paid
```

**Fly.io:**
```bash
fly secrets set \
  CARBON_MESH_EIA_API_KEY=xxx \
  CARBON_MESH_GRID_STATUS_API_KEY=xxx \
  CARBON_MESH_ENTSOE_TOKEN=xxx \
  CARBON_MESH_AUTO_MIGRATE=true
```

**Render** — Environment tab in dashboard, or set in `render.yaml`:
```yaml
# render.yaml already has placeholders — fill them in the Render dashboard
```

**Railway** — Variables tab in dashboard:
```
CARBON_MESH_EIA_API_KEY = xxx
CARBON_MESH_GRID_STATUS_API_KEY = xxx
CARBON_MESH_ENTSOE_TOKEN = xxx
```

**Docker Compose** — edit `.env` (loaded via `env_file`):
```bash
# Same as local dev — docker-compose.yml reads .env automatically
```

### Step 3: Verify

```bash
curl https://your-app.fly.dev/health/providers
```
```json
{
  "configured": {
    "EIA (US grid)": true,
    "GridStatus (US ISOs)": true,
    "UK Carbon Intensity": true,
    "AEMO (Australia)": true,
    "...": true
  },
  "missing": {
    "Electricity Maps (global)": false
  },
  "total_configured": 9,
  "total_available": 10
}
```

### No-Key Providers (work immediately)

These providers require no credentials and are always active:

| Provider | Coverage | Method |
|----------|----------|--------|
| UK Carbon Intensity | Great Britain (18 zones, 30-min) | Direct API |
| AEMO | Australia (5 states, 5-min) | Direct API |
| Grid India | India (5 regions) | Heuristic model |
| ONS Brazil | Brazil (5 regions) | Heuristic model |
| Eskom | South Africa | Heuristic model |
| Open-Meteo | Worldwide (40+ zones) | Weather-based estimation |

---

## API Reference

Interactive docs at `/docs` (Swagger) or `/redoc` (ReDoc) when the server is running.

### Core Routing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/route` | POST | Find the greenest region for your workload |
| `/api/v1/regions` | GET | List all 75+ supported cloud regions |
| `/api/v1/regions?provider=aws` | GET | Filter regions by provider |
| `/api/v1/carbon/{provider}/{region}` | GET | Get live carbon intensity for a region |
| `/api/v1/accounting/savings` | GET | Carbon savings report |

### Billing & Usage

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/billing/plans` | GET | List available plans (Free/Pro/Enterprise) |
| `/api/v1/billing/status` | GET | Current usage and tier status |

### Admin (requires `CARBON_MESH_ADMIN_SECRET`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/api-keys` | POST | Create a new API key |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe (version, DB status, carbon source) |
| `/ready` | GET | Readiness probe (503 if DB unreachable) |
| `/health/providers` | GET | Which data providers have credentials configured |
| `/metrics` | GET | Prometheus metrics |
| `/ws/carbon` | WS | Real-time carbon intensity stream |
| `/docs` | GET | Swagger UI |
| `/redoc` | GET | ReDoc |

### Example: Route a Workload

```bash
curl -X POST http://localhost:8000/api/v1/route \
  -H "Content-Type: application/json" \
  -d '{
    "constraints": {
      "providers": ["aws", "gcp", "azure"],
      "carbon_weight": 1.0,
      "cost_weight": 0.0
    }
  }'
```

```json
{
  "recommended": {
    "provider": "aws",
    "region": "ca-central-1",
    "grid_zone": "CA-ON",
    "carbon_intensity_gco2_kwh": 12.3,
    "renewable_percentage": 95.2,
    "score": 0.0,
    "carbon_savings_vs_worst_pct": 98.1
  },
  "alternatives": ["..."],
  "request_id": "a1b2c3d4",
  "timestamp": "2026-03-12T10:30:00Z"
}
```

### Example: Constrain by Data Residency

```bash
curl -X POST http://localhost:8000/api/v1/route \
  -H "Content-Type: application/json" \
  -d '{
    "constraints": {
      "providers": ["aws", "gcp", "azure"],
      "data_residency": ["EU"],
      "carbon_weight": 0.7,
      "cost_weight": 0.3
    }
  }'
```

---

## Data Sources

Carbon Mesh cascades through 11 data providers, using the most accurate source available for each grid zone:

| # | Provider | Coverage | Resolution | Auth |
|---|----------|----------|-----------|------|
| 1 | UK Carbon Intensity | UK (18 zones) | 30 min | Free, no key |
| 2 | EIA (US DOE) | US (60+ balancing authorities) | Hourly | Free key |
| 3 | AEMO | Australia (5 states) | 5 min | Free, no key |
| 4 | Grid India | India (5 regions) | Heuristic | Free, no key |
| 5 | ONS Brazil | Brazil (5 regions) | Heuristic | Free, no key |
| 6 | Eskom | South Africa | Heuristic | Free, no key |
| 7 | GridStatus.io | US ISOs (7) | 5 min | Free key |
| 8 | ENTSO-E | Europe (36+ countries) | Hourly | Free token |
| 9 | Open-Meteo | Worldwide (40+ zones) | Hourly | Free, no key |
| 10 | Electricity Maps | Global (200+ zones) | Real-time | Paid key |
| 11 | Mock (fallback) | All zones | Static | None |

**Priority chain:** UK > EIA > AEMO > Grid India > ONS Brazil > Eskom > GridStatus > ENTSO-E > Open-Meteo > Electricity Maps > Mock

## Cloud Region Coverage

75+ cloud regions across three major providers:

- **AWS** — 26 regions (us-east-1, eu-west-1, ap-southeast-2, af-south-1, ...)
- **GCP** — 37 regions (us-central1, europe-north1, australia-southeast1, ...)
- **Azure** — 35 regions (eastus, norwayeast, australiaeast, ...)

Each region is mapped to a physical electricity grid zone in `data/region_grid_map.yaml`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Data Sources** | | |
| `CARBON_MESH_CARBON_SOURCE` | `hybrid` | Mode: `hybrid`, `mock`, `eia`, `gridstatus`, `electricity_maps` |
| `CARBON_MESH_EIA_API_KEY` | | EIA API key ([free](https://www.eia.gov/opendata/)) |
| `CARBON_MESH_GRID_STATUS_API_KEY` | | GridStatus API key ([free](https://www.gridstatus.io/)) |
| `CARBON_MESH_ENTSOE_TOKEN` | | ENTSO-E token ([free](https://transparency.entsoe.eu/)) |
| `CARBON_MESH_ELECTRICITY_MAPS_API_KEY` | | Electricity Maps key (paid) |
| `CARBON_MESH_CACHE_TTL_SECONDS` | `300` | Cache TTL for grid data |
| **Server** | | |
| `CARBON_MESH_HOST` | `0.0.0.0` | Bind address |
| `CARBON_MESH_PORT` | `8000` | Bind port |
| `CARBON_MESH_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| **Database** | | |
| `CARBON_MESH_USE_DATABASE` | `false` | Enable Postgres persistence |
| `CARBON_MESH_DATABASE_URL` | `postgresql+asyncpg://...` | Postgres URL (auto-normalizes `postgres://`) |
| `CARBON_MESH_AUTO_MIGRATE` | `false` | Run Alembic migrations on startup |
| **Auth** | | |
| `CARBON_MESH_API_KEY_REQUIRED` | `false` | Require `X-API-Key` header |
| `CARBON_MESH_ADMIN_SECRET` | | Secret for admin endpoints |
| **Limits** | | |
| `CARBON_MESH_RATE_LIMIT_DEFAULT` | `100/minute` | Default rate limit |
| `CARBON_MESH_RATE_LIMIT_ROUTE` | `30/minute` | Route endpoint rate limit |
| **Observability** | | |
| `CARBON_MESH_LOG_FORMAT` | `text` | `text` for dev, `json` for production |
| `CARBON_MESH_LOG_LEVEL` | `INFO` | Python log level |

---

## Architecture

```
src/carbon_mesh/
  api/              FastAPI routes + dependency injection + WebSocket
  auth/             API key generation, hashing, validation
  billing/          Usage tracking, tier limits, plan management
  carbon_sources/   11 pluggable data providers (Protocol-based)
  engine/           Routing engine + multi-objective scorer + TTL cache
  grid/             Cloud region <-> electricity grid zone mapper
  models/           Pydantic domain models
  accounting/       Per-request carbon tracking + savings reports
  db/               SQLAlchemy async models + Alembic migrations
  cli/              Typer CLI (carbon-mesh route, intensity, regions)
  config.py         Environment-based config with validation
  logging_config.py Structured JSON logging for production
  main.py           FastAPI app, middleware, lifespan

web/                Vite + React + TypeScript frontend
  src/pages/        Landing, Dashboard, RouteDemo, Plans, Settings, 404
  src/components/   Nav, ErrorBoundary
  src/api/          Typed API client + WebSocket types

terraform/          Terraform data source for green routing
data/               region_grid_map.yaml (75+ regions -> grid zones)
alembic/            Database migrations
tests/              117 tests across 8 files
```

```
                    ┌──────────────┐
                    │   Frontend   │  Vercel / Netlify / nginx
                    │  (React/Vite)│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   API Server │  Fly.io / Render / Railway
                    │   (FastAPI)  │
                    └──┬───┬───┬───┘
                       │   │   │
              ┌────────┘   │   └────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Postgres │ │  Carbon  │ │Prometheus│
        │  (state) │ │  Data    │ │ /metrics │
        └──────────┘ │ Providers│ └──────────┘
                     └──────────┘
                     EIA, ENTSO-E, UK,
                     AEMO, GridStatus, ...
```

## Development

```bash
make help       # show all commands
make setup      # install deps + copy .env + build frontend
make dev        # API + frontend with hot reload
make test       # 117 tests
make lint       # ruff + tsc
make fix        # auto-fix lint
make migrate    # run Alembic migrations
make up         # docker compose (Postgres + API + Web)
make down       # stop everything
```

## The SaaS Vision

Carbon Mesh is building toward a full compute platform — not just a routing API, but a place where you deploy workloads and we handle the green routing transparently.

**Think Hetzner pricing, but every server runs on verified clean energy.**

### What's Built
- Real-time carbon intensity monitoring across 90+ grid zones from 11 providers
- Multi-cloud region scoring and routing engine with configurable carbon/cost weights
- Carbon accounting with per-request savings tracking
- Usage-based billing tiers (Free: 100/day, Pro: 10k/day, Enterprise: unlimited)
- API key auth with SHA-256 hashing + rate limiting
- WebSocket real-time carbon intensity streaming
- React dashboard with live feed, provider status, plans page
- Terraform integration for IaC green routing
- GitHub Actions composite action for CI/CD carbon routing
- One-click deploy to Render, Fly.io, Railway, Docker Compose
- Prometheus metrics, structured JSON logging, health/readiness probes
- 117 tests, pre-commit hooks, comprehensive CI/CD

### What's Next (Compute Plane)
- **Managed compute** — Deploy containers/VMs, auto-placed on cleanest infrastructure
- **Temporal shifting** — Queue non-urgent jobs to run during green energy windows
- **Live migration** — Migrate long-running workloads as grid conditions change
- **Carbon SLA** — Contractual guarantee: "Your workload ran on >90% renewable energy"
- **Kubernetes operator** — `kubectl apply` and Carbon Mesh picks the greenest cluster
- **Stripe integration** — Live billing with Pro/Enterprise payment processing

## License

MIT
