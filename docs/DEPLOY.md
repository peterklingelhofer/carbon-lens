# Deploying Carbon Mesh

Carbon Mesh is designed for one-click deployment. Pick your platform:

## Quick Start (any platform)

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/carbon-mesh-control-plane.git
cd carbon-mesh-control-plane
make setup   # installs deps, copies .env, builds frontend

# 2. Add API keys to .env (all free, no credit card)
#    See "Getting API Keys" below

# 3. Run locally
make up       # Docker: Postgres + API + Frontend
# OR
make dev      # Dev mode with hot reload
```

## One-Click Deploy

### Render (recommended for getting started)
1. Fork this repo
2. Go to [render.com/deploy](https://render.com) → New Blueprint Instance
3. Point to your repo — Render reads `render.yaml` automatically
4. Add API keys in the Render dashboard (Environment tab)
5. Done! Render provisions Postgres + API + Frontend automatically

### Fly.io
```bash
fly launch --copy-config --yes          # Creates app from fly.toml
fly postgres create                      # Managed Postgres
fly postgres attach                      # Injects DATABASE_URL
fly secrets set CARBON_MESH_EIA_API_KEY=xxx CARBON_MESH_AUTO_MIGRATE=true
fly deploy
```

### Railway
1. Connect repo at [railway.app](https://railway.app)
2. Add a Postgres plugin (one click)
3. Railway reads `railway.toml` automatically
4. Set env vars in dashboard
5. Deploy

### Docker Compose (self-hosted)
```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up -d
```

### Vercel + Fly.io (split deploy)
- **Frontend** → Vercel: connect repo, set root to `web/`, set `VITE_API_URL`
- **Backend** → Fly.io: follow Fly.io steps above
- Update `web/vercel.json` rewrites to point to your Fly.io URL

### Netlify + Fly.io (split deploy)
- **Frontend** → Netlify: connect repo, set base directory to `web/`
- **Backend** → Fly.io: follow Fly.io steps above
- Update `web/netlify.toml` redirects to point to your Fly.io URL

## Getting API Keys (all free)

| Provider | Coverage | Sign Up | Env Var |
|----------|----------|---------|---------|
| **EIA** | US grid (real-time) | [eia.gov/opendata](https://www.eia.gov/opendata/) | `CARBON_MESH_EIA_API_KEY` |
| **GridStatus** | US ISOs (CAISO, ERCOT, etc.) | [gridstatus.io](https://www.gridstatus.io/) | `CARBON_MESH_GRID_STATUS_API_KEY` |
| **ENTSO-E** | Europe (35 countries) | [transparency.entsoe.eu](https://transparency.entsoe.eu/) | `CARBON_MESH_ENTSOE_TOKEN` |
| **Electricity Maps** | Global (paid, optional) | [electricitymaps.com](https://api-portal.electricitymaps.com/) | `CARBON_MESH_ELECTRICITY_MAPS_API_KEY` |

**No-key providers** (work out of the box):
- UK Carbon Intensity API
- AEMO (Australia)
- Open-Meteo (weather/solar/wind estimates)
- Grid India, ONS Brazil, Eskom (heuristic models)

After adding keys, verify at: `GET /health/providers`

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CARBON_MESH_CARBON_SOURCE` | `hybrid` | Data source mode |
| `CARBON_MESH_USE_DATABASE` | `false` | Enable Postgres persistence |
| `CARBON_MESH_DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection string |
| `CARBON_MESH_API_KEY_REQUIRED` | `false` | Require X-API-Key header |
| `CARBON_MESH_ADMIN_SECRET` | `` | Secret for admin endpoints |
| `CARBON_MESH_AUTO_MIGRATE` | `false` | Run Alembic migrations on startup |
| `CARBON_MESH_LOG_FORMAT` | `text` | `text` or `json` |
| `CARBON_MESH_LOG_LEVEL` | `INFO` | Python log level |
| `CARBON_MESH_RATE_LIMIT_DEFAULT` | `100/minute` | Default rate limit |
| `CARBON_MESH_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

## Verify Your Deployment

```bash
# Health check
curl https://your-app.fly.dev/health

# Provider status — see which data sources have credentials
curl https://your-app.fly.dev/health/providers

# Route a workload
curl -X POST https://your-app.fly.dev/api/v1/route \
  -H "Content-Type: application/json" \
  -d '{"constraints": {"providers": ["aws", "gcp"], "carbon_weight": 1.0, "cost_weight": 0.0}}'

# Interactive API docs
open https://your-app.fly.dev/docs
```

## Architecture

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
                     EIA, ENTSO-E,
                     UK API, AEMO,
                     GridStatus, ...
```
