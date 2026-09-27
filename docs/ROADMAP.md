# Roadmap

[README.md](../README.md) describes what's built and is kept current.
This page lists what isn't built yet.

## What's next

- Market-based Scope 2 accounting (RECs/PPAs) and supplier-specific Scope 3 factors
- Utilization-aware energy modeling. The current model assumes a flat draw per vCPU-hour
- Signed PDF reports and a recognized attestation standard
- Report templates for CSRD (as PDF), SEC climate disclosure and California SB 253
- Live-account validation of the billing adapters
- Global consumption-based intensity. It needs paid cross-border flow data, so tracing
  is EU-only (free ENTSO-E) today
- A sharper "cleaner than usual" baseline as the history archive accumulates
- More cloud providers and on-prem coverage
- Measured marginal emissions in place of the fuel-mix heuristic, if a data budget appears
- Email and Slack alerting for SLA breaches
- Per-key API usage metering and rate limits (queries per key per day)
- Historical intensity in Postgres. The archive is a set of published snapshot files today
- Workload region tracking from AWS CloudWatch or GCP Monitoring
- A GitLab CI template against this API. The companion
  [carbon-aware-dispatcher](https://github.com/peterklingelhofer/carbon-aware-dispatcher)
  already ships one against its own providers
- A Terraform *provider*: `data "carbonlens_greenest_region" {}`. A
  [module](../deploy/terraform/greenest-region/README.md) ships today
