# Terraform: greenest region to deploy

A tiny Terraform module that asks CarbonLens which cloud region is greenest for a
**permanent** deployment — by *typical* (history-mean) carbon intensity, the honest
basis for an always-on workload — and exposes it as outputs. Use it to set a
provider's `region` at `apply` time, so a new deployment lands on clean power by
default.

Region choice is the highest-leverage carbon decision: a region can be many times
cleaner, forever. This makes "pick the clean one" the path of least resistance.

## Usage

```hcl
module "greenest" {
  source          = "github.com/peterklingelhofer/carbonlens//deploy/terraform/greenest-region"
  cloud_providers = "aws"        # restrict to one cloud you deploy on
  power_watts     = 500          # optional: get an annual kg estimate
}

provider "aws" {
  region = module.greenest.region   # deploy to the greenest AWS region
}

output "carbon_choice" {
  value = "${module.greenest.region} (~${module.greenest.typical_gco2_kwh} gCO2/kWh)"
}
```

Restrict the choice (e.g. data residency or where you have quota) with
`candidate_regions = "us-west-2,us-east-1,eu-west-1"`.

## Inputs

| Variable | Default | Description |
|----------|---------|-------------|
| `api_url` | public instance | CarbonLens API base URL. |
| `cloud_providers` | `aws,gcp,azure` | Comma-separated providers to consider. |
| `candidate_regions` | `""` | Optional comma-separated region names to restrict to. |
| `power_watts` | `null` | Optional continuous load (W) for an annual kg estimate. |

## Outputs

`provider`, `region`, `grid_zone`, `typical_gco2_kwh`, `annual_kg`.

## Honest limits

- The choice is read at **plan** time and pinned into state. Re-run `terraform apply`
  periodically to re-evaluate as grids change; it won't move a running deployment on
  its own.
- Typical intensity is a history mean (falling back to the current reading where
  history is thin) — directional guidance for siting, not a guarantee. Pin
  `candidate_regions` to where you actually have latency/residency/quota constraints.
- Only the `hashicorp/http` provider is required; no credentials needed to read it.
