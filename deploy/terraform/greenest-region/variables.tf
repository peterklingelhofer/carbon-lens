variable "api_url" {
  type        = string
  default     = "https://carbonlens-gssa.onrender.com"
  description = "CarbonLens API base URL. Point at your own deployment for production."
}

variable "cloud_providers" {
  type        = string
  default     = "aws,gcp,azure"
  description = "Comma-separated providers to consider (aws, gcp, azure)."
}

variable "candidate_regions" {
  type        = string
  default     = ""
  description = "Optional comma-separated region names to restrict the choice to."
}

variable "power_watts" {
  type        = number
  default     = null
  description = "Optional continuous load (W) for an annual kg-CO2 estimate per region."
}
