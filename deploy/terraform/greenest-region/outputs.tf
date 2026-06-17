output "provider" {
  value       = local.best.provider
  description = "Greenest cloud provider for a permanent deployment."
}

output "region" {
  value       = local.best.region
  description = "Greenest region -- wire into your provider block's region."
}

output "grid_zone" {
  value       = local.best.grid_zone
  description = "Electricity grid zone the region sits on."
}

output "typical_gco2_kwh" {
  value       = local.best.typical_gco2_kwh
  description = "Typical (history-mean) carbon intensity of the chosen region."
}

output "annual_kg" {
  value       = local.best.annual_kg
  description = "Estimated annual kg CO2 at power_watts (null if not provided)."
}
