# Pick the greenest cloud region to deploy into, at `terraform apply` time, from
# CarbonLens' /carbon/siting (greenest region by TYPICAL carbon intensity -- the
# honest basis for an always-on deployment). The http data source is read during
# plan, so the outputs are known early enough to configure a cloud provider's region.

locals {
  query = join("&", compact([
    "providers=${var.cloud_providers}",
    var.candidate_regions != "" ? "candidate_regions=${var.candidate_regions}" : "",
    var.power_watts != null ? "power_watts=${var.power_watts}" : "",
  ]))

  siting = jsondecode(data.http.siting.response_body)
  best   = local.siting.recommended
}

data "http" "siting" {
  url = "${var.api_url}/api/v1/carbon/siting?${local.query}"
  request_headers = {
    Accept = "application/json"
  }
}
