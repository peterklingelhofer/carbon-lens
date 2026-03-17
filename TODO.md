# Carbon Mesh — Carbon Data API + Compliance Platform

## Product Vision
**Carbon Mesh** is a real-time carbon intensity data API and compliance reporting platform.
We aggregate 11 government-verified carbon data sources into a single developer-friendly API,
and provide turnkey CSRD/SEC/SB-253 compliance reporting for cloud workloads.

---

## Phase 1: Rebrand & Restructure (Pre-Launch) — COMPLETE

### Frontend
- [x] Rewrite Landing page hero + features for Carbon Data API + Compliance
- [x] Rename "Broker" nav → "API Explorer" (interactive carbon data playground)
- [x] Create API Explorer page (test carbon queries, view response, code snippets)
- [x] Update Plans page copy (API queries/day, compliance reports, SLA monitoring)
- [x] Reorder nav: Home | API Explorer | Grid Data | Compliance | SLA | Route | Plans | Orgs | Settings
- [x] Update Dashboard subtitle (emphasize "API powering your compliance")
- [x] Clean up ZK-specific types and API client methods

### README
- [x] Rewrite for Carbon Data API + Compliance Platform positioning
- [x] Remove ZK Broker as primary product (keep as "Use Case" section)
- [x] Add API-first documentation with code examples (curl, Python, JS)
- [x] Update "The Vision" section
- [x] Update architecture diagram

### Backend (Config & Routes)
- [x] Add `/api/v1/carbon/zones` endpoint — list all supported grid zones
- [ ] Add `/api/v1/carbon/history/{zone}` endpoint — historical carbon data
- [ ] Add `/api/v1/carbon/forecast/{zone}` endpoint — carbon forecast (where available)
- [ ] Add API key usage metering middleware (count queries per key per day)
- [x] Add `/api/v1/status/sources` — health/latency of each carbon data source

### Backend (Compliance Enhancements)
- [ ] Add cloud bill CSV upload endpoint (AWS Cost & Usage Report format)
- [ ] Add GCP billing export ingestion
- [ ] Add Azure cost export ingestion
- [ ] CSRD template — downloadable PDF report
- [ ] SEC climate disclosure template
- [ ] California SB 253 report template

---

## Phase 2: Green SLA Monitoring — COMPLETE (core)

### Backend (15 new endpoints)
- [x] `POST /api/v1/sla/create` — define carbon SLA (max gCO2/kWh, min renewable %)
- [x] `GET /api/v1/sla/list` — list SLAs for an organization
- [x] `GET /api/v1/sla/{id}` — get SLA definition
- [x] `PUT /api/v1/sla/{id}` — update SLA targets
- [x] `DELETE /api/v1/sla/{id}` — delete an SLA
- [x] `POST /api/v1/sla/{id}/check` — on-demand compliance check
- [x] `GET /api/v1/sla/{id}/status` — current SLA compliance status
- [x] `GET /api/v1/sla/{id}/checks` — list compliance check history
- [x] `POST /api/v1/sla/{id}/report` — SLA attestation report for auditors
- [x] `GET /api/v1/sla/{id}/reports` — list attestation reports
- [x] `POST /api/v1/sla/monitor/start` — start background monitoring
- [x] `POST /api/v1/sla/monitor/stop` — stop background monitoring
- [x] `GET /api/v1/sla/monitor/status` — monitor status
- [x] `GET /api/v1/sla/monitor/alerts` — recent breach alerts

### SLA Engine
- [x] SLAEngine — compliance checks against live carbon data
- [x] Region resolution (all regions for providers, or specific regions)
- [x] Status classification (compliant / warning / breached)
- [x] Attestation report generation with daily breakdown
- [x] Worst/best region analysis

### Background Monitor
- [x] SLAMonitor — asyncio background worker
- [x] Configurable check frequency (hourly / daily / weekly)
- [x] Webhook alerts on breach
- [x] Alert history with bounded storage

### Frontend
- [x] SLA Monitor page (create, check, report, monitor controls)
- [x] Status badges (compliant/warning/breached)
- [x] Interactive SLA creation with carbon/renewable sliders
- [x] Check result display with breached regions table
- [x] Attestation report viewer

### Tests (19 new)
- [x] Model tests (7): SLA, Check, Status enum, Summary, Alert, Report, Frequency
- [x] Engine tests (8): Compliant, Breached, Specific regions, No regions, Renewable breach, Report generation, Empty report, Summarize
- [x] Monitor tests (3): Status, Start/Stop, Alerts

### Remaining (requires accounts)
- [ ] Connect to AWS CloudWatch / GCP Monitoring for workload region tracking
- [ ] Quarterly attestation PDF generation (needs PDF library)
- [ ] Email alerting (needs SMTP config)
- [ ] Slack alerting (needs Slack app)

---

## Phase 3: Carbon-Aware Scheduling — COMPLETE (core)

### Backend (7 endpoints)
- [x] `POST /api/v1/scheduler/find-window` — find optimal low-carbon time window
- [x] `GET /api/v1/scheduler/now` — greenest region right now
- [x] `POST /api/v1/scheduler/schedules` — create recurring schedule
- [x] `GET /api/v1/scheduler/schedules` — list schedules for org
- [x] `GET /api/v1/scheduler/schedules/{id}` — get schedule
- [x] `DELETE /api/v1/scheduler/schedules/{id}` — delete schedule
- [x] `POST /api/v1/scheduler/schedules/{id}/next` — next optimal window

### Scheduling Engine
- [x] SchedulingEngine — multi-region, multi-provider evaluation
- [x] Three strategies: lowest carbon, highest renewable, balanced
- [x] Time-of-day heuristic projection (solar + demand curves)
- [x] Carbon savings calculation (vs running immediately)
- [x] Preferred regions filtering

### Frontend
- [x] Scheduler page with interactive controls (duration, delay, strategy, providers)
- [x] Greenest-region-now live card
- [x] Recommendation display with alternatives table
- [x] Integration examples (GitHub Actions, Python SDK)
- [x] Nav link added

### Tests (16 new)
- [x] Model tests (4): Strategy enum, TimeSlot, CronSchedule, ScheduleRecommendation
- [x] Engine tests (8): Basic, lowest carbon, highest renewable, preferred regions, single provider, no regions fallback, carbon savings, multi-hour window
- [x] Heuristic tests (4): Solar factor, demand factor, score slot (3 strategies)

### Remaining (future)
- [ ] Kubernetes admission controller (delay pods to green windows)
- [ ] GitHub Actions plugin (run CI in greenest region)
- [ ] Terraform provider (select region at plan time)
- [ ] Real weather-based forecasting (replace heuristics with actual forecast data)
- [ ] Database persistence for schedules (currently in-memory)

---

## Phase 4: Integrations & Partnerships

- [ ] Electricity Maps data enrichment partnership
- [ ] WattTime integration as additional source
- [ ] Cloud provider partnerships (AWS/GCP/Azure carbon API access)
- [ ] Accounting software integrations (export to sustainability reporting tools)

---

## ZK Broker (Retained as Use Case / Demo)
The ZK broker code is retained in `src/carbon_mesh/zk/` as a demonstration of
carbon-aware compute routing. It showcases the platform's capabilities but is
no longer the primary product. No further ZK-specific development unless
there's customer demand.

---

## Account Setup (Required for Production)

### Carbon Data API Keys (5 minutes)
- [ ] EIA API key — https://www.eia.gov/opendata/
- [ ] GridStatus API key — https://www.gridstatus.io/
- [ ] ENTSO-E token — https://transparency.entsoe.eu/
- [ ] Electricity Maps key (optional, paid) — https://api-portal.electricitymaps.com/

### Stripe Billing (15 minutes)
- [ ] Create Stripe account
- [ ] Configure products/prices matching Free/Pro/Enterprise tiers
- [ ] Set `CARBON_MESH_STRIPE_SECRET_KEY` and `CARBON_MESH_STRIPE_PRICE_ID_*`

### Deployment
- [ ] Choose platform (Fly.io / Render / Railway)
- [ ] Set environment variables
- [ ] Enable PostgreSQL for persistence
- [ ] Configure custom domain
- [ ] Set up monitoring (Grafana / Datadog)
