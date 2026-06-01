# CarbonLens SaaS Roadmap

## Where We Are Now (Control Plane MVP)

What's built:
- Real-time carbon intensity monitoring (11 providers, 90+ grid zones)
- Multi-cloud routing engine (AWS/GCP/Azure, 75+ regions)
- REST API (route, regions, carbon intensity, accounting)
- Carbon savings tracking per request
- 57 tests passing

What's missing to become a real SaaS:

---

## Phase 1: API-as-a-Service (Month 1-2)

**Goal:** People can sign up, get an API key, and integrate CarbonLens into their existing deployment pipelines.

### Auth & Multi-tenancy
- [ ] API key authentication (issue keys per org)
- [ ] Rate limiting per API key (free tier: 100 req/day, paid: unlimited)
- [ ] Tenant isolation for carbon accounting (each org sees only their data)

### Persistence
- [ ] PostgreSQL for accounting records, API keys, org data
- [ ] Replace in-memory tracker with DB-backed tracker
- [ ] Historical carbon intensity data (store every query for trend analysis)

### Billing
- [ ] Stripe integration for usage-based billing
- [ ] Free tier: 100 route requests/day, mock data only
- [ ] Pro tier ($29/mo): Unlimited requests, live grid data, carbon dashboard
- [ ] Enterprise: Custom pricing, SLA, dedicated support

### CLI Tool
- [ ] `carbon-mesh route --providers aws,gcp --residency EU`
- [ ] `carbon-mesh intensity aws/us-east-1`
- [ ] `carbon-mesh report --last 30d`
- [ ] Publish to PyPI: `pip install carbon-mesh`

### CI/CD Integrations
- [ ] GitHub Action: `uses: carbon-mesh/route@v1` — sets `DEPLOY_REGION` output
- [ ] GitLab CI template
- [ ] Terraform provider: `data "carbon_mesh_greenest_region" {}`

---

## Phase 2: Managed Compute (Month 3-6)

**Goal:** Users deploy workloads directly to CarbonLens. We handle placement on the cleanest infrastructure. Think "Hetzner meets green routing."

### Compute Provisioning
- [ ] Hetzner Cloud API integration (cheapest bare-metal provider, EU-focused, actual green DC in Finland)
- [ ] AWS spot instance provisioning via boto3
- [ ] GCP preemptible VM provisioning
- [ ] Azure spot VM provisioning
- [ ] Unified compute API: `POST /compute/deploy` → we pick the region

### Pricing Model (Hetzner-competitive)
Target: match or beat Hetzner on price for equivalent specs, with the green guarantee as the differentiator.

| Tier | vCPU | RAM | Storage | Price | Notes |
|------|------|-----|---------|-------|-------|
| Starter | 2 | 4 GB | 40 GB SSD | $4.50/mo | Hetzner CX22 is $4.35 |
| Standard | 4 | 8 GB | 80 GB SSD | $8.50/mo | Hetzner CX32 is $7.85 |
| Performance | 8 | 16 GB | 160 GB SSD | $16/mo | Hetzner CX42 is $14.75 |
| Compute | 16 | 32 GB | 320 GB SSD | $30/mo | Hetzner CX52 is $28.55 |

The premium over Hetzner (~5-15%) pays for:
- Carbon-verified placement (provable, auditable)
- Multi-cloud redundancy (not locked to one provider)
- Automatic region migration when grid gets dirty
- Carbon SLA (contractual guarantee)

For batch/flexible workloads (CI/CD, ML training), prices can be *lower* than Hetzner by using spot instances in green regions during off-peak hours.

### Container Platform
- [ ] Docker container deployment: `carbon-mesh deploy --image myapp:latest`
- [ ] Automatic region selection based on current grid conditions
- [ ] Container registry (or integrate with existing: GHCR, DockerHub, ECR)
- [ ] Health checks, auto-restart, logging

### Temporal Shifting (for non-urgent jobs)
- [ ] `POST /compute/queue` with `deadline_hours: 24`
- [ ] System finds the greenest window within the deadline
- [ ] Returns `scheduled_at` and `estimated_carbon_intensity`
- [ ] Webhook notification when job completes
- [ ] Ideal for: ML training, video transcoding, nightly builds, data pipelines

---

## Phase 3: Platform (Month 6-12)

**Goal:** Full platform with dashboard, Kubernetes integration, and carbon SLAs.

### Carbon Dashboard (Frontend)
- [ ] Real-time world map showing grid carbon intensity
- [ ] Per-org dashboard: total carbon saved, greenest jobs, trends
- [ ] Badge generator: "Powered by CarbonLens — 94% renewable this month"
- [ ] Scope 3 emissions report export (PDF/CSV) for ESG compliance

### Kubernetes Operator
- [ ] `CarbonMeshCluster` CRD — define multi-region cluster pool
- [ ] Scheduler plugin: pods get placed on greenest available node
- [ ] `carbon-mesh.io/min-renewable: "80%"` annotation on deployments
- [ ] Auto-migration: reschedule pods when grid conditions change
- [ ] Works with EKS, GKE, AKS

### Carbon SLA
- [ ] Contractual guarantee: "Your workload ran on >X% renewable energy"
- [ ] Backed by auditable government grid data (not self-reported)
- [ ] SLA breach → automatic credit
- [ ] Tiers: 80% renewable ($X), 90% ($X+), 95% ($X++)

### Live Migration
- [ ] For long-running workloads (web apps, databases)
- [ ] Monitor grid conditions continuously
- [ ] When current region drops below threshold, migrate to cleaner region
- [ ] Requires stateless or replicated workloads (or managed DB replication)

---

## Phase 4: Scale (Month 12+)

### Edge Network
- [ ] CDN-like edge nodes in the greenest locations
- [ ] Static asset serving from renewable-powered edge
- [ ] Anycast DNS routing to cleanest healthy edge

### Carbon API Marketplace
- [ ] Third-party developers build on CarbonLens data
- [ ] "Carbon intensity as a service" for non-compute use cases
- [ ] IoT, EV charging, smart home energy optimization

### Carbon Credits
- [ ] Issue verifiable carbon reduction certificates
- [ ] Based on actual measured savings (counterfactual vs. chosen region)

---

## Technical Decisions

### Why Hetzner as First Compute Provider
1. **Price leader** — Cheapest reliable cloud in Europe
2. **Green data centers** — Hetzner's Finland DC (Helsinki) runs on the Nordic grid (~95% clean)
3. **No "green premium" markup** — They don't charge extra for it
4. **Simple API** — Easy to provision programmatically
5. **EU data residency** — GDPR-friendly by default

### Why Not Just Wrap Existing Providers
Wrapping AWS/GCP/Azure adds their markup (~3-10x over bare metal). For CarbonLens to be price-competitive with Hetzner:
- Use bare-metal/VPS providers (Hetzner, OVH, Vultr) as the primary compute layer
- Use hyperscalers only for regions where bare-metal isn't available
- Pass through near-cost pricing + small CarbonLens fee

### Pricing Strategy
1. **Control plane (API):** Free tier + $29/mo pro — this is the land. Low friction, developers try it.
2. **Compute:** Hetzner-competitive pricing — this is the expand. Once people see the carbon dashboard, they want managed compute.
3. **Enterprise:** Carbon SLA + Scope 3 reporting — this is the monetize. Big companies will pay premium for auditable green compute for ESG compliance.

---

## Key Competitive Advantages

1. **Government-verified data** — We use official grid operator data (EIA, ENTSO-E, AEMO), not self-reported corporate numbers
2. **Hourly, not annual** — We track actual grid conditions per hour, not annual averages
3. **Multi-cloud** — Not locked to one provider. We arbitrage across all of them.
4. **Open source control plane** — Transparent methodology. Anyone can verify our claims.
5. **Price competitive** — Green doesn't have to cost more. Clean energy during off-peak is often the cheapest energy.
