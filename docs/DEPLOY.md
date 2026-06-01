# Deploying CarbonLens

CarbonLens is designed for one-click deployment. Pick your platform:

## Free public demo (stateless — no DB, no API keys)

The carbon-by-zone demo needs no database and no provider keys: the `hybrid`
source cascades down to heuristic estimators and a mock fallback when no keys
are present. This makes a genuinely free, scale-to-zero public demo possible.

**Architecture:** static frontend on Cloudflare Pages + scale-to-zero API on Fly.io.

### 1. Deploy the API to Fly.io

`fly.toml` is preconfigured for this: `min_machines_running = 0`,
`CARBON_LENS_USE_DATABASE = "false"`, `CARBON_LENS_API_KEY_REQUIRED = "false"`,
and a `/ready` healthcheck that passes without a database.

```bash
fly launch --copy-config --yes   # uses fly.toml as-is; no Postgres needed
fly deploy
```

If the app name `carbon-mesh` is taken, Fly will assign another — note the real
`*.fly.dev` URL it prints, then update `web/.env.production` (step 2) and the
`CARBON_LENS_CORS_ORIGINS` value in `fly.toml` to match, and `fly deploy` again.

### 2. Deploy the frontend to Cloudflare Pages

The build reads `web/.env.production` (committed), which points at the Fly URL:

```
VITE_API_URL=https://carbon-mesh.fly.dev
VITE_WS_URL=wss://carbon-mesh.fly.dev
```

In the Cloudflare Pages dashboard → Create project → connect this repo:
- **Root directory:** `web`
- **Build command:** `npm run build`
- **Output directory:** `dist`

Cloudflare gives you `https://<project>.pages.dev`. The default `fly.toml`
already allow-lists `https://carbon-mesh.pages.dev` in CORS — if your project
name differs, update `CARBON_LENS_CORS_ORIGINS` in `fly.toml` and `fly deploy`.

### 3. Verify

```bash
curl https://carbon-mesh.fly.dev/ready          # {"status":"ready"}
open https://<project>.pages.dev/dashboard       # the live UI
```

Cold start is ~1-2s after idle (Fly stops the machine at 0 connections).

### 4. Real, live data without burning API quotas (the snapshot)

To serve **real** data — not the mock fallback — while surviving a traffic
spike on free API keys, the dashboard reads a pre-built snapshot instead of
calling providers per request. The `snapshot` GitHub Action
([.github/workflows/snapshot.yml](../.github/workflows/snapshot.yml)) runs
[scripts/build_snapshot.py](../scripts/build_snapshot.py) every 30 minutes,
pulls every region from the real providers, and force-pushes `snapshot.json`
to a dedicated `data` branch. The frontend fetches that file from GitHub's
Fastly CDN (`raw.githubusercontent.com/.../data/snapshot.json`).

Why this stays free and quota-safe:
- The **only** caller of the provider APIs is the cron — `zones x 48 runs/day`,
  independent of how many people view the site. A CDN absorbs all viewer
  traffic, so a spike cannot blow through your free keys.
- Keys live in **GitHub Secrets**, used only in CI — never shipped to the browser.
- `data` is a separate branch, so snapshots never trigger a Cloudflare Pages
  rebuild (which has a free-tier build cap).

Setup (one time):
1. Get free keys: **EIA** ([eia.gov/opendata](https://www.eia.gov/opendata/),
   instant), **ENTSO-E** ([transparency.entsoe.eu](https://transparency.entsoe.eu/),
   token ~1 day), plus your existing **GridStatus** key. UK + Australia need none.
2. Add them as repo **Settings → Secrets and variables → Actions**:
   - `CARBON_LENS_EIA_API_KEY`
   - `CARBON_LENS_ENTSOE_TOKEN`
   - `CARBON_LENS_GRID_STATUS_API_KEY`
3. Run the workflow once (**Actions → Carbon snapshot → Run workflow**) to
   create the `data` branch.
4. Confirm `web/.env.production` `VITE_SNAPSHOT_URL` points at your `data` branch
   (already set for `peterklingelhofer/carbonlens`), then redeploy the frontend.

The dashboard banner then reads e.g. *"34 grid zones live from real
grid-operator APIs · 6 estimated · updated 4 min ago. No mock data."* Mock
readings are dropped by the builder, so they can never reach the demo. Zones
whose live API is intermittent (e.g. Grid India) show an amber `est.` tag
instead of disappearing. The build **fails** (and keeps the last good snapshot)
if fewer than 5 zones come back live — so a missing/expired key surfaces in CI
rather than silently degrading the demo.

Run it locally to see the split:

```bash
CARBON_LENS_EIA_API_KEY=... CARBON_LENS_ENTSOE_TOKEN=... \
  CARBON_LENS_GRID_STATUS_API_KEY=... \
  uv run python scripts/build_snapshot.py --out snapshot.json
```

> If the demo ever goes viral, swap the `raw.githubusercontent.com` URL for a
> Cloudflare R2 public bucket (free egress) — the workflow's publish step is the
> only thing to change.

---

## Quick Start (any platform)

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/carbonlens.git
cd carbonlens
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
fly secrets set CARBON_LENS_EIA_API_KEY=xxx CARBON_LENS_AUTO_MIGRATE=true
fly deploy
```

### Railway / other Dockerfile PaaS
Any platform that builds from a `Dockerfile` works without a platform-specific
config: point it at this repo's root `Dockerfile`, add a Postgres plugin, set the
env vars (including `CARBON_LENS_AUTO_MIGRATE=true`), and set the health check to
`/ready`.

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
| **EIA** | US grid (real-time) | [eia.gov/opendata](https://www.eia.gov/opendata/) | `CARBON_LENS_EIA_API_KEY` |
| **GridStatus** | US ISOs (CAISO, ERCOT, etc.) | [gridstatus.io](https://www.gridstatus.io/) | `CARBON_LENS_GRID_STATUS_API_KEY` |
| **ENTSO-E** | Europe (35 countries) | [transparency.entsoe.eu](https://transparency.entsoe.eu/) | `CARBON_LENS_ENTSOE_TOKEN` |
| **Electricity Maps** | Global (paid, optional) | [electricitymaps.com](https://api-portal.electricitymaps.com/) | `CARBON_LENS_ELECTRICITY_MAPS_API_KEY` |

**No-key providers** (work out of the box):
- UK Carbon Intensity API
- AEMO (Australia)
- Open-Meteo (weather/solar/wind estimates)
- Grid India, ONS Brazil, Eskom (heuristic models)

After adding keys, verify at: `GET /health/providers`

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CARBON_LENS_CARBON_SOURCE` | `hybrid` | Data source mode |
| `CARBON_LENS_USE_DATABASE` | `false` | Enable Postgres persistence |
| `CARBON_LENS_DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection string |
| `CARBON_LENS_API_KEY_REQUIRED` | `false` | Require X-API-Key header |
| `CARBON_LENS_ADMIN_SECRET` | `` | Secret for admin endpoints |
| `CARBON_LENS_AUTO_MIGRATE` | `false` | Run Alembic migrations on startup |
| `CARBON_LENS_LOG_FORMAT` | `text` | `text` or `json` |
| `CARBON_LENS_LOG_LEVEL` | `INFO` | Python log level |
| `CARBON_LENS_RATE_LIMIT_DEFAULT` | `100/minute` | Default rate limit |
| `CARBON_LENS_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

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
                    │   API Server │  Fly.io / Render / Docker
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
