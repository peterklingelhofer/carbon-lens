# Carbon Mesh

**Real-time carbon intensity data API + compliance reporting platform.**

Carbon Mesh aggregates 11 government-verified electricity grid data sources into a single developer-friendly API. Know the exact carbon intensity of any cloud region, any time. Generate CSRD/SEC/SB-253 compliance reports. Monitor Green SLAs.

## Why This Exists

Every major cloud provider claims "100% renewable energy." They're not. They use **annual REC matching** — buying solar credits at noon to offset coal burned at midnight. Your 2 AM batch job in Virginia runs on 70% fossil fuels. The provider just buys offsets later.

**Carbon Mesh gives you the real numbers.** Real-time gCO2/kWh for every cloud region, every minute, from government sources — not corporate sustainability reports.

---

## Quick Start

```bash
git clone https://github.com/your-org/carbon-mesh-control-plane.git
cd carbon-mesh-control-plane
make setup    # install deps, copy .env, build frontend
make dev      # API on :8000 + frontend on :5173
```

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

client = httpx.Client(base_url="https://api.carbonmesh.dev", headers={"X-API-Key": "your_key"})

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
const res = await fetch("https://api.carbonmesh.dev/api/v1/carbon/aws/us-east-1", {
  headers: { "X-API-Key": "your_key" }
});
const { carbon_intensity_gco2_kwh, renewable_percentage } = await res.json();
```

---

## Products

### 1. Carbon Intensity API
Real-time electricity grid carbon data for 90+ cloud regions worldwide. 11 data sources with cascading fallback.

| Feature | Free | Pro ($99/mo) | Enterprise |
|---------|------|-------------|------------|
| API queries/day | 100 | 50,000 | Unlimited |
| Data sources | 6 (no-key) | All 11 | All 11 + custom |
| Resolution | Hourly | 5-min | 5-min |
| Regions | 75+ | 75+ | 75+ + custom |
| Support | Community | Email | Dedicated |

### 2. Compliance Reporting
Turnkey CSRD / SEC Climate / California SB 253 emissions reporting for cloud workloads.

- **Scope 2** location-based and market-based emissions
- **Scope 3** Category 1 (purchased cloud services)
- **GHG Protocol** aligned methodology
- **EU Taxonomy** eligibility assessment
- Export as JSON, CSV, or PDF

### 3. Carbon-Aware Routing
Route workloads to the greenest cloud region in real-time. Works with AWS, GCP, and Azure.

### 4. Green SLA Monitoring (Coming Soon)
Continuous monitoring + quarterly attestation reports proving your workloads met carbon targets.

---

## Data Sources

Carbon Mesh cascades through 11 providers, using the most accurate source for each grid zone:

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

Carbon Mesh works out of the box with 6 no-key providers. Add API keys for more real-time government data:

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
  cli/              Typer CLI (carbon-mesh route, intensity, regions)
  zk/               Carbon-aware compute demo (ZK proof routing)
  config.py         Environment-based config with validation
  main.py           FastAPI app, middleware, lifespan

web/                Vite + React 19 + TypeScript frontend
  src/pages/        Landing, API Explorer, Dashboard, Compliance, Plans, Settings, Orgs
  src/api/          Typed API client + WebSocket

terraform/          Terraform data source for green routing
data/               region_grid_map.yaml (75+ regions -> grid zones)
alembic/            Database migrations
tests/              217 tests
```

```
                ┌──────────────┐
                │   Frontend   │  Vercel / Netlify
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
| **Render** | New Blueprint Instance | `render.yaml` |
| **Fly.io** | `fly launch --copy-config --yes` | `fly.toml` |
| **Railway** | Connect repo | `railway.toml` |
| **Docker** | `make up` | `docker-compose.yml` |
| **Vercel** (frontend) | Connect repo, root = `web/` | `web/vercel.json` |

---

## Development

```bash
make help       # show all commands
make setup      # install deps + copy .env + build frontend
make dev        # API + frontend with hot reload
make test       # 217 tests
make lint       # ruff + tsc
make fix        # auto-fix lint
make migrate    # run Alembic migrations
make up         # docker compose
make down       # stop everything
```

---

## The Vision

Carbon Mesh is a **carbon data infrastructure company**. We provide the real-time data layer
that powers carbon-aware decisions across the cloud computing industry.

**What's built:**
- Real-time carbon intensity API with 11 government-verified data sources
- 75+ cloud regions mapped to electricity grid zones
- CSRD/ESRS E1 compliance reporting with Scope 2+3 emissions
- Carbon-aware routing engine (find the greenest region)
- Multi-tenant SaaS with Stripe billing
- React dashboard with live WebSocket carbon feeds
- 217 tests, one-click deploy

**What's next:**
- Green SLA monitoring and attestation
- Cloud bill ingestion (AWS/GCP/Azure)
- Carbon-aware Kubernetes scheduler
- Historical carbon data and forecasting API
- PDF compliance report generation

## License

MIT
