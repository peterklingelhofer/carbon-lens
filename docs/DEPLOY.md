# Deploying CarbonLens

CarbonLens is designed for one-click deployment. Pick your platform:

## Greenest free deployment

A carbon tool should run on clean power. You can't get a literal 100%
carbon-free grid on a free tier (those grids — Iceland geothermal, Nordic and
Québec hydro — are paid-region only; see the upgrade path below), but this stack
gets genuinely low-carbon for $0 and, more importantly, **uses almost no
electricity in the first place.**

**The architecture is the biggest lever.** Absolute footprint ≈ energy used ×
grid intensity. This design drives the first term to near-zero:

- **Frontend is a static CDN** — viewer traffic hits cached edge files, not a
  server. A traffic spike costs you no extra compute.
- **API scales to zero** — it draws power only while actively serving a request,
  then sleeps (`min_machines_running = 0` on Fly; free Render services spin down
  when idle).
- **The only scheduled work is a ~1-minute snapshot job every 30 minutes.**

Using almost no power beats buying renewable certificates for power you didn't
need to burn. That's the honest sustainability story — no overclaiming a "100%
green" that every host fudges via annual certificate matching.

**Then pick the cleanest free placement on top of that:**

| Piece | Greenest free choice | Why |
|-------|----------------------|-----|
| **API** | **Render free → Oregon region** | Pacific-NW grid (BPAT) is hydro-heavy — one of the cleanest grids in North America, well below the US average. CarbonLens's own snapshot measures it (`us-west2`). |
| **Frontend** | **Cloudflare Workers** (static assets) | Free, global CDN, and the most explicit renewable-matching commitment of the static hosts. (Cloudflare Pages works too; you just can't pin a region on either — edge nodes are everywhere.) |
| **Snapshot cron** | **GitHub Actions** | Runs on Azure-hosted runners (renewable-matched). Region isn't user-selectable on the free tier — but the job is ~1 min/run, so its energy is negligible. |

### Pinning the API to Oregon on Render
When creating the Render Web Service (see the Render steps below), set
**Region → Oregon** in the dashboard before deploying. Everything else (free
plan, Docker, `/ready` health check, env vars) is unchanged. That single
dropdown is what puts the only always-on-ish piece on the cleanest free grid.

### Upgrade path to literal 24/7 carbon-free (paid)
If a budget ever opens up, move just the API to a near-100%-carbon-free grid —
no code changes, only a region/host swap:

- **Fly.io → Stockholm (`arn`)** — Swedish grid (hydro + nuclear) is ~carbon-free
  almost every hour. `fly.toml` already targets a scale-to-zero machine; set
  `primary_region = "arn"`.
- **Azure/GCP Nordic or Québec regions** (Norway, Sweden, `canadaeast`) for the
  same physical-grid benefit.

True 24/7 carbon-free (every hour, not annual averages) is an industry frontier;
a Nordic/Québec hydro region is the closest you can practically get, and it's a
one-line region change here.

## Free public demo (stateless — no DB, no API keys)

The carbon-by-zone demo needs no database and no provider keys: the `hybrid`
source cascades down to heuristic estimators and a mock fallback when no keys
are present. This makes a genuinely free, scale-to-zero public demo possible.

**Live architecture:** static frontend on **Cloudflare Workers** (static assets)
+ scale-to-zero API on **Render** (Oregon). This is what
[carbonlens.peterklingelhofer.workers.dev](https://carbonlens.peterklingelhofer.workers.dev)
runs on, talking to the API at `https://carbonlens-gssa.onrender.com`.

### 1. Deploy the API to Render (Oregon)

Follow the **Render free Web Service** steps under
[One-Click Deploy](#one-click-deploy) below — stateless, scale-to-zero, and
**Region → Oregon** (the PNW hydro grid). You get a `https://<name>.onrender.com`
URL.

### 2. Deploy the frontend to Cloudflare Workers

The build reads `web/.env.production` (committed), which points at the Render API:

```
VITE_API_URL=https://carbonlens-gssa.onrender.com
VITE_WS_URL=wss://carbonlens-gssa.onrender.com
```

`web/wrangler.jsonc` serves the built `dist/` as Worker static assets with SPA
fallback (so `/globe`, `/dashboard`, etc. resolve). Build and deploy:

```bash
cd web
npm run build
npx wrangler deploy        # uploads dist/ → https://<name>.workers.dev
```

(Cloudflare Pages also works if you prefer the dashboard flow: connect the repo,
root directory `web`, build `npm run build`, output `dist`.)

### 3. Allow the frontend origin (CORS)

In the **Render dashboard → Environment**, set the API's allowlist to your
frontend origin and redeploy:

```
CARBON_LENS_CORS_ORIGINS=["https://carbonlens.peterklingelhofer.workers.dev","http://localhost:5173"]
```

(The snapshot-backed pages — Dashboard, Globe — read GitHub's CDN directly and
work regardless; CORS only gates the interactive API pages like the API Explorer.)

### 4. Verify

```bash
curl https://carbonlens-gssa.onrender.com/ready              # {"status":"ready"}
open https://carbonlens.peterklingelhofer.workers.dev/        # the live UI
```

First request after idle cold-starts in ~50s (Render spins the free service down
when idle; the [ColdStartBanner](../web/src/components/ColdStartBanner.tsx) covers
that in the UI).

### 5. Real, live data without burning API quotas (the snapshot)

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

### 6. Durable SLA monitoring (optional)

The public demo is stateless, so SLAs live in memory and reset on restart. To make
SLA definitions, checks, and reports survive restarts, point the API at a Postgres
database — everything else is automatic:

```bash
CARBON_LENS_USE_DATABASE=true
CARBON_LENS_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

Run `uv run alembic upgrade head` once (or on deploy) to create the tables.

**Keep it permanently free:** Render's bundled free Postgres is time-limited
(deleted after ~30 days), so for a lasting free DB point `CARBON_LENS_DATABASE_URL`
at a free **Neon** or **Supabase** instance instead — no code change, just the URL.

**Scheduled checks on a scale-to-zero host:** the in-process monitor only runs
while the API is awake, so a free instance that spins down won't check on schedule.
The [`sla-monitor.yml`](../.github/workflows/sla-monitor.yml) GitHub Actions cron
solves this — it POSTs hourly to the admin-only `/api/v1/sla/monitor/run`, which
runs any due checks and persists them (and wakes the instance). Configure two
repo settings: variable `SLA_API_URL` (your API origin) and secret
`CARBON_LENS_ADMIN_SECRET` (matching the API's admin secret). Unset → the job
no-ops, so it's safe in forks.

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

### Render free Web Service — stateless API (used by the green stack)
This is the API half of the recommended green deployment: one free, stateless,
scale-to-zero service on the cleanest free region. Use **New → Web Service**,
**not** "Blueprint" (the Blueprint provisions a Postgres + second service this
demo doesn't need).

1. [dashboard.render.com](https://dashboard.render.com) → **New + → Web Service**
   → connect this repo.
2. **Runtime:** Docker (auto-detects the root `Dockerfile`).
   **Branch:** `main`. **Instance type:** Free. **Health check path:** `/ready`.
3. **Region → Oregon** — the one green choice that matters: PNW hydro grid.
4. Environment variables:
   ```
   CARBON_LENS_USE_DATABASE        false
   CARBON_LENS_API_KEY_REQUIRED    false
   CARBON_LENS_CARBON_SOURCE       hybrid
   CARBON_LENS_LOG_FORMAT          json
   CARBON_LENS_EIA_API_KEY         <your EIA key>
   CARBON_LENS_GRID_STATUS_API_KEY <your GridStatus key>
   CARBON_LENS_ENTSOE_TOKEN        <when it arrives>
   CARBON_LENS_CORS_ORIGINS        ["https://<your-frontend>.workers.dev"]
   ```
5. **Create Web Service.** You get `https://<name>.onrender.com`. Verify
   `…/ready` returns `{"status":"ready"}`. First request after idle cold-starts
   in ~50s (the [ColdStartBanner](../web/src/components/ColdStartBanner.tsx)
   covers that in the UI).

### Render Blueprint (full stack with Postgres — not the green/free path)
1. Fork this repo
2. Go to [render.com/deploy](https://render.com) → New Blueprint Instance
3. Point to your repo — Render reads `render.yaml` automatically
4. Add API keys in the Render dashboard (Environment tab)
5. Done! Render provisions Postgres + API + Frontend automatically
   (note: the free Postgres expires after 90 days, and this runs always-on —
   prefer the stateless Web Service above for the low-carbon demo)

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
curl https://carbonlens-gssa.onrender.com/health

# Provider status — see which data sources have credentials
curl https://carbonlens-gssa.onrender.com/health/providers

# Route a workload
curl -X POST https://carbonlens-gssa.onrender.com/api/v1/route \
  -H "Content-Type: application/json" \
  -d '{"constraints": {"providers": ["aws", "gcp"], "carbon_weight": 1.0, "cost_weight": 0.0}}'

# Interactive API docs (Swagger UI)
open https://carbonlens-gssa.onrender.com/docs
```

## Architecture

```
                    ┌──────────────┐
                    │   Frontend   │  Cloudflare Workers / Pages
                    │  (React/Vite)│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   API Server │  Render / Fly.io / Docker
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
