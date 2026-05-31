# CarbonLens Terraform Data Source
#
# This uses Terraform's built-in HTTP data source to query the CarbonLens API
# for the greenest cloud region. No custom provider needed.
#
# Usage:
#   1. Start the CarbonLens API: `uv run serve`
#   2. Run: `terraform init && terraform plan`
#
# The output `greenest_region` can be used in other resources:
#   region = data.external.carbon_mesh_route.result.region

variable "carbon_mesh_api_url" {
  description = "CarbonLens API base URL"
  type        = string
  default     = "http://localhost:8000"
}

variable "providers" {
  description = "Cloud providers to consider"
  type        = list(string)
  default     = ["aws", "gcp", "azure"]
}

variable "data_residency" {
  description = "Data residency constraint (e.g. EU, US)"
  type        = list(string)
  default     = []
}

variable "carbon_weight" {
  description = "Carbon optimization weight (0-1)"
  type        = number
  default     = 1.0
}

# Use the external data source to call the CarbonLens API
data "external" "carbon_mesh_route" {
  program = ["bash", "-c", <<-EOT
    RESPONSE=$(curl -sf -X POST "${var.carbon_mesh_api_url}/api/v1/route" \
      -H "Content-Type: application/json" \
      -d '{
        "constraints": {
          "providers": ${jsonencode(var.providers)},
          ${length(var.data_residency) > 0 ? "\"data_residency\": ${jsonencode(var.data_residency)}," : ""}
          "carbon_weight": ${var.carbon_weight},
          "cost_weight": ${1 - var.carbon_weight}
        }
      }')

    echo "$RESPONSE" | jq '{
      provider: .recommended.provider,
      region: .recommended.region,
      grid_zone: .recommended.grid_zone,
      carbon_intensity: (.recommended.carbon_intensity_gco2_kwh | tostring),
      renewable_percentage: (.recommended.renewable_percentage | tostring),
      carbon_savings_pct: (.recommended.carbon_savings_vs_worst_pct | tostring)
    }'
  EOT
  ]
}

output "greenest_region" {
  description = "The greenest cloud region based on current grid conditions"
  value = {
    provider             = data.external.carbon_mesh_route.result.provider
    region               = data.external.carbon_mesh_route.result.region
    grid_zone            = data.external.carbon_mesh_route.result.grid_zone
    carbon_intensity     = data.external.carbon_mesh_route.result.carbon_intensity
    renewable_percentage = data.external.carbon_mesh_route.result.renewable_percentage
    carbon_savings_pct   = data.external.carbon_mesh_route.result.carbon_savings_pct
  }
}

# Example: Use the result to deploy an AWS EC2 instance in the greenest region
#
# resource "aws_instance" "green_workload" {
#   ami           = "ami-0c55b159cbfafe1f0"
#   instance_type = "t3.micro"
#
#   # Deploy in the greenest region!
#   provider = aws.${data.external.carbon_mesh_route.result.region}
#
#   tags = {
#     Name       = "green-workload"
#     GridZone   = data.external.carbon_mesh_route.result.grid_zone
#     Renewable  = "${data.external.carbon_mesh_route.result.renewable_percentage}%"
#   }
# }
