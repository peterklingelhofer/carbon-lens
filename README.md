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

## Green ZK Proof Broker

Carbon Mesh doubles as a **Green ZK Proof Broker** — routing zero-knowledge proof generation to GPU compute powered by 100% renewable energy, and earning bounties from decentralized prover networks.

### How It Works

```
Prover Networks                   Carbon Mesh Broker                     Green GPU Compute
(Boundless, Succinct,      ┌─────────────────────────────┐      (IREN hydro, Hive Digital
 Scroll, Aleo, Gevulot,    │  1. Poll for proof jobs      │       geothermal, TeraWulf
 zkSync, StarkNet, Taiko)  │  2. Check carbon intensity   │       hydro, Bitdeer hydro,
         │                 │  3. Filter: only 100% green  │       + AWS/GCP spot)
         │  bounty jobs    │  4. Score: carbon × cost     │            │
         ├────────────────►│  5. Check profitability      │────────────┤
         │                 │  6. Provision GPU             │  provision │
         │                 │  7. Run prover Docker image   │────────────►
         │                 │  8. Verify proof locally      │  ◄─ proof ─┤
         │  ◄── proof ─────│  9. Submit proof on-chain     │            │
         │                 │  10. Claim bounty             │  terminate │
         │  ◄── bounty ───│  11. Terminate GPU            │────────────►
         │                 └─────────────────────────────┘
```

### You Don't Need Rust

Each prover network ships **Docker containers** with compiled Rust/C++ provers inside. The broker orchestrates — it doesn't compute. The prover runtime module maps all 8 networks to their Docker images and handles witness preparation, container execution with `--gpus all` passthrough, and proof collection.

### ZK Broker API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/zk/jobs/available` | GET | Poll all prover networks for bounty jobs |
| `/api/v1/zk/jobs/evaluate` | POST | Evaluate a job — find greenest profitable GPU |
| `/api/v1/zk/jobs/execute` | POST | Full pipeline: evaluate + prove + verify + submit + claim |
| `/api/v1/zk/jobs/{id}/status` | GET | Get job status and result |
| `/api/v1/zk/jobs/{id}/cancel` | POST | Cancel a running job |
| `/api/v1/zk/jobs/active` | GET | List currently executing jobs |
| `/api/v1/zk/simulate` | POST | Simulate routing for a hypothetical job |
| `/api/v1/zk/stats` | GET | Aggregate broker statistics |
| `/api/v1/zk/metrics` | GET | Detailed metrics (throughput, revenue, carbon) |
| `/api/v1/zk/events` | GET | Recent job lifecycle events |
| `/api/v1/zk/policy` | GET/PUT | Get or update carbon routing policy |
| `/api/v1/zk/compute/available` | GET | List GPU options with live carbon data |
| `/api/v1/zk/compute/spot-prices` | GET | Live GPU spot prices from all providers |
| `/api/v1/zk/runtime/networks` | GET | Supported prover networks + Docker images |
| `/api/v1/zk/runtime/verifiers` | GET | Check available proof verifiers |
| `/api/v1/zk/wallet` | GET | Broker wallet address and balance |
| `/api/v1/zk/poller/status` | GET | Background job poller status |
| `/api/v1/zk/poller/start` | POST | Start auto-polling for bounty jobs |
| `/api/v1/zk/poller/stop` | POST | Stop the background poller |

### Supported Networks

| Network | Proof System | Docker Image | Min VRAM | Typical Bounty |
|---------|-------------|--------------|----------|----------------|
| Boundless | RISC Zero | `risczero/risc0-groth16-prover` | 16 GB | $2.50-$8.00 |
| Succinct | SP1 | `succinctlabs/sp1-prover` | 16 GB | $3.75 |
| Scroll | HALO2 | `scrolltech/scroll-prover` | 40 GB | $15.00 |
| Aleo | Groth16 | `aleohq/snarkos-prover` | 8 GB | $1.80 |
| Gevulot | STARK | `gevulot/prover` | 24 GB | $12.00 |
| zkSync | PLONK | `matterlabs/zksync-prover` | 24 GB | Varies |
| StarkNet | STARK | `starkware/stone-prover` | CPU | Varies |
| Taiko | RISC Zero | `taikoxyz/raiko` | 16 GB | Varies |

### Green GPU Compute Providers

| Provider | Location | Energy Source | Pricing | Interruption |
|----------|----------|---------------|---------|--------------|
| IREN | British Columbia | 100% hydro | $0.65/hr RTX 4090 | 0% (dedicated) |
| Hive Digital | Iceland | 100% geothermal | $0.90/hr A100 40GB | 0% |
| Hive Digital | Sweden | 99% hydro+wind | $0.60/hr RTX 4090 | 0% |
| TeraWulf | New York | 95% hydro | $0.70/hr RTX 4090 | 0% |
| Bitdeer | Norway | 99% hydro | $1.00/hr A100 80GB | 0% |
| CoreWeave | New York | Grid-connected | $2.49/hr H100 | 0% |
| Lambda Labs | Texas | Grid-connected | $1.29/hr A100 80GB | 0% |
| Vast.ai | Global | Varies | $0.40/hr RTX 4090 | 15% |
| AWS Spot | us-east-1 | Grid-connected | $1.10/hr A100 40GB | 5% |
| GCP Preemptible | us-central1 | Grid-connected | $0.35/hr T4 | 10% |

---

## Going Live: Account Setup Guide

Everything below is required to earn real bounties. The broker software is fully built — these are the external accounts and configuration steps to connect it to live networks.

### Phase 1: Ethereum Wallet (15 minutes)

You need an Ethereum wallet to submit proofs and receive bounties.

| Step | Action | Details |
|------|--------|---------|
| 1 | **Install a wallet** | Use [MetaMask](https://metamask.io/) (browser) or generate a key with `cast wallet new` (Foundry) |
| 2 | **Export private key** | In MetaMask: Account Details > Export Private Key |
| 3 | **Fund with ETH** | Buy ETH on Coinbase/Kraken, send to your wallet. Need ~0.05 ETH ($125) for gas |
| 4 | **Configure broker** | Set `CARBON_MESH_ZK_WALLET_PRIVATE_KEY=0x...` in `.env` |
| 5 | **Set chain ID** | Mainnet: `CARBON_MESH_ZK_WALLET_CHAIN_ID=1`. For testing: Sepolia = `11155111` |

**Security**: Never commit your private key. Use environment variables or a secrets manager. In production, use a hardware wallet (Ledger/Trezor) or KMS-backed signer.

### Phase 2: Prover Network Registration (1-2 hours)

Register as a prover on one or more networks. Start with Boundless or Succinct — they have the simplest onboarding.

#### Boundless (RISC Zero) — Recommended First Network

| Step | Action | Link |
|------|--------|------|
| 1 | Create account on Boundless marketplace | https://boundless.xyz |
| 2 | Register your wallet address as a prover | Dashboard > Become a Prover |
| 3 | Stake required tokens (if applicable) | Follow network-specific staking guide |
| 4 | Note your prover ID / API key | Add to `.env` as `BOUNDLESS_PROVER_KEY` |
| 5 | Test with a small job on testnet first | Boundless Sepolia testnet available |

#### Succinct (SP1)

| Step | Action | Link |
|------|--------|------|
| 1 | Sign up on Succinct Network | https://succinct.xyz |
| 2 | Register as a prover operator | Network > Operators |
| 3 | Configure SP1 prover endpoint | Follow SP1 prover docs |

#### Scroll

| Step | Action | Link |
|------|--------|------|
| 1 | Apply to Scroll's prover program | https://scroll.io |
| 2 | Scroll uses a permissioned prover set initially | May require application/approval |
| 3 | Run their prover client alongside the broker | Follow Scroll prover documentation |

#### Aleo

| Step | Action | Link |
|------|--------|------|
| 1 | Install `snarkOS` | https://github.com/AleoHQ/snarkOS |
| 2 | Create an Aleo account | `snarkos account new` |
| 3 | Fund with Aleo credits for staking | Purchase on exchanges or mine |
| 4 | Register as a prover | `snarkos start --prover` |

#### Gevulot

| Step | Action | Link |
|------|--------|------|
| 1 | Join the Gevulot prover network | https://gevulot.com |
| 2 | Register your node | Follow their prover registration docs |
| 3 | No staking required initially | CPU proofs accepted |

### Phase 3: GPU Compute Access (30 minutes - 1 week)

You need access to GPU machines. Two paths:

#### Path A: Green Datacenter Contracts (Recommended)

These provide dedicated, behind-the-meter renewable GPU access with zero interruption risk.

| Provider | How to Get Access | Expected Timeline |
|----------|-------------------|-------------------|
| **IREN** | Contact sales: [iren.com](https://iren.com) | 1-2 weeks |
| **Hive Digital** | Contact: [hivedigital.com](https://www.hivedigital.com) | 1-2 weeks |
| **TeraWulf** | Contact: [terawulf.com](https://terawulf.com) | 1-2 weeks |
| **Bitdeer** | Contact: [bitdeer.com](https://bitdeer.com) | 1-2 weeks |

Once you have SSH access, configure in `.env`:
```bash
CARBON_MESH_ZK_SSH_HOSTS='{"iren": {"host": "gpu1.iren.com", "port": 22, "user": "prover", "key_path": "~/.ssh/iren_key"}}'
CARBON_MESH_ZK_COMPUTE_BACKEND=ssh
```

#### Path B: Cloud Spot Instances (Faster, but grid-connected)

| Provider | Setup | GPU Options |
|----------|-------|-------------|
| **AWS** | Create account at [aws.amazon.com](https://aws.amazon.com), request GPU quota increase for `p4d.24xlarge` (A100) or `g5.xlarge` (A10G) spot instances | A100, T4, A10G |
| **GCP** | Create account at [cloud.google.com](https://cloud.google.com), enable Compute Engine API, request GPU quota | A100, T4, L4 |
| **CoreWeave** | Apply at [coreweave.com](https://coreweave.com) | H100, A100, RTX 4090 |
| **Lambda Labs** | Sign up at [lambdalabs.com](https://lambdalabs.com) | A100, H100 |
| **Vast.ai** | Sign up at [vast.ai](https://vast.ai), fund account with crypto/credit card | RTX 4090, A100 |

**Note**: Cloud spot instances run on the local electricity grid, which may include fossil fuels. The broker's carbon policy engine will filter these out if they exceed your carbon threshold. Only behind-the-meter green datacenters guarantee 100% renewable at all times.

### Phase 4: Enable the Executor (5 minutes)

Once accounts are set up, enable the full execution pipeline:

```bash
# .env
CARBON_MESH_ZK_EXECUTOR_ENABLED=true
CARBON_MESH_ZK_MAX_CONCURRENT_JOBS=4
CARBON_MESH_ZK_AUTO_CLAIM_BOUNTY=true
CARBON_MESH_ZK_WALLET_PRIVATE_KEY=0x...your_private_key...
CARBON_MESH_ZK_WALLET_CHAIN_ID=1
CARBON_MESH_ZK_COMPUTE_BACKEND=ssh  # or "local_docker" for testing
```

### Phase 5: Go Live Checklist

- [ ] Ethereum wallet funded with ETH for gas (~0.05 ETH)
- [ ] Registered as prover on at least one network
- [ ] GPU compute access configured (SSH hosts or cloud credentials)
- [ ] Prover Docker images pulled and tested locally
- [ ] Proof verifier binaries or Docker images available
- [ ] Carbon policy configured (default: max 50 gCO2/kWh, min 80% renewable)
- [ ] Profit margin threshold set (default: 10%)
- [ ] Run a test job on testnet/devnet first
- [ ] Monitor the `/api/v1/zk/metrics` endpoint
- [ ] Enable the background poller for 24/7 autopilot

### Testing Without Live Accounts

The broker works fully in simulation mode without any accounts:

```bash
# Start the server
uv run serve

# Simulate routing a $5 Boundless job
curl -X POST http://localhost:8000/api/v1/zk/simulate \
  -H "Content-Type: application/json" \
  -d '{"network": "boundless", "bounty_usd": 5.0, "circuit_size": 20}'

# View all available mock jobs
curl http://localhost:8000/api/v1/zk/jobs/available

# Check spot prices
curl http://localhost:8000/api/v1/zk/compute/spot-prices

# View supported prover networks and Docker images
curl http://localhost:8000/api/v1/zk/runtime/networks
```

---

## Architecture

```
src/carbon_mesh/
  api/              FastAPI routes + dependency injection + WebSocket
  auth/             API key generation, hashing, validation
  billing/          Usage tracking, tier limits, plan management
  carbon_sources/   11 pluggable data providers (Protocol-based)
  compliance/       CSRD-aligned emissions measurement and reporting
  engine/           Routing engine + multi-objective scorer + TTL cache
  grid/             Cloud region <-> electricity grid zone mapper
  models/           Pydantic domain models (routing, carbon, ZK broker)
  accounting/       Per-request carbon tracking + savings reports
  db/               SQLAlchemy async models + Alembic migrations
  cli/              Typer CLI (carbon-mesh route, intensity, regions)
  zk/               Green ZK Proof Broker
    orchestrator.py   Job evaluation, carbon filtering, profitability gating
    executor.py       Full pipeline: provision -> prove -> verify -> submit -> claim
    gpu_lifecycle.py  GPU instance management (local Docker + SSH backends)
    prover_runtime.py Docker image registry for 8 prover networks
    verification.py   Local proof verification (native + Docker + structural)
    wallet.py         Ethereum wallet, tx building, gas estimation
    spot_prices.py    Live GPU spot price feeds from all providers
    persistence.py    Job state persistence (in-memory + PostgreSQL)
    monitoring.py     Prometheus metrics, structured events, activity feed
    poller.py         Background job discovery across all prover networks
    prover_networks.py Prover network adapters (mock + real protocols)
    compute_providers.py GPU compute provider adapters
    routes.py         20 API endpoints for the broker
  config.py         Environment-based config with validation
  logging_config.py Structured JSON logging for production
  main.py           FastAPI app, middleware, lifespan

web/                Vite + React 19 + TypeScript frontend
  src/pages/        Landing, Dashboard, ZKBroker, Compliance, Plans, Settings, Orgs
  src/components/   Nav, ErrorBoundary
  src/api/          Typed API client + WebSocket types

terraform/          Terraform data source for green routing
data/               region_grid_map.yaml (75+ regions -> grid zones)
alembic/            Database migrations (6 versions)
tests/              217 tests across 9 files
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
        │ Postgres │ │  Carbon  │ │  Green   │
        │  (state) │ │  Data    │ │  GPU     │
        └──────────┘ │ Providers│ │ Compute  │
                     └──────────┘ └──────────┘
                     EIA, ENTSO-E,  IREN, Hive,
                     UK, AEMO, ...  TeraWulf, ...
                           │              │
                    ┌──────▼──────────────▼──┐
                    │   Prover Networks      │
                    │ Boundless, Succinct,   │
                    │ Scroll, Aleo, Gevulot  │
                    └────────────────────────┘
```

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
| **ZK Broker** | | |
| `CARBON_MESH_ZK_EXECUTOR_ENABLED` | `false` | Enable full job execution pipeline |
| `CARBON_MESH_ZK_MAX_CONCURRENT_JOBS` | `4` | Max parallel proof jobs |
| `CARBON_MESH_ZK_AUTO_CLAIM_BOUNTY` | `true` | Auto-claim bounties after proof submission |
| `CARBON_MESH_ZK_COMPUTE_BACKEND` | `local_docker` | `local_docker`, `ssh`, or `mock` |
| `CARBON_MESH_ZK_WALLET_PRIVATE_KEY` | | Ethereum private key (never commit!) |
| `CARBON_MESH_ZK_WALLET_CHAIN_ID` | `1` | 1=mainnet, 11155111=sepolia testnet |
| `CARBON_MESH_ZK_SSH_HOSTS` | | JSON map of SSH hosts for green datacenters |
| **Observability** | | |
| `CARBON_MESH_LOG_FORMAT` | `text` | `text` for dev, `json` for production |
| `CARBON_MESH_LOG_LEVEL` | `INFO` | Python log level |

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
make up         # docker compose (Postgres + API + Web)
make down       # stop everything
```

## The Vision

Carbon Mesh is a **Green ZK Proof Broker** — earning crypto bounties by routing zero-knowledge proof generation to GPU compute powered by 100% renewable energy.

### What's Built
- **ZK Broker**: Full execution pipeline — poll jobs, evaluate profitability, provision GPU, run prover, verify proof, submit on-chain, claim bounty
- **8 prover networks**: Boundless, Succinct, Scroll, Aleo, Gevulot, zkSync, StarkNet, Taiko
- **12 GPU compute providers**: 5 green datacenters (100% renewable) + 3 hyperscaler spot + 4 alt-cloud
- **Carbon policy engine**: Only dispatch to compute meeting carbon thresholds (default: max 50 gCO2/kWh, min 80% renewable)
- **Deadline-aware scheduling**: Rejects jobs that can't complete before deadline
- **Spot interruption retry**: Auto-retries on GPU preemption (up to 2 retries with deadline check)
- **Background job poller**: 24/7 autopilot polling all prover networks for profitable jobs
- **Proof verification**: Local verification before on-chain submission (prevents gas waste and slashing)
- **Wallet scaffolding**: Transaction building, gas estimation, bounty claiming
- **Live spot pricing**: Real-time GPU prices from all providers with 5-minute cache
- **Monitoring**: Prometheus metrics, job throughput, revenue/profit tracking, carbon impact, event feed
- **Durable persistence**: PostgreSQL-backed job state with full lifecycle tracking
- **React dashboard**: Job execution UI, autopilot controls, activity feed, stats
- **11 carbon data sources**: Real-time grid carbon intensity for every compute region
- **217 tests** across 9 test files
- One-click deploy to Render, Fly.io, Railway, Docker Compose

### What's Next (Requires Accounts)
- **Live prover network connections** — Replace mock adapters with real WebSocket/API clients
- **Live GPU provisioning** — Replace mock providers with real cloud API integrations
- **On-chain proof submission** — Fund wallet, broadcast built transactions
- **Staking** — Stake tokens on networks that require it
- **Real bounty claiming** — Fill in contract addresses, connect to live markets

## License

MIT
