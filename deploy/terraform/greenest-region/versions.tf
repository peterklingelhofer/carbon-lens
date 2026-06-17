terraform {
  required_version = ">= 1.3"
  required_providers {
    http = {
      source  = "hashicorp/http"
      version = ">= 3.0"
    }
  }
}
