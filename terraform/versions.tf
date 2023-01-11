# main.tf
terraform {
  required_version = ">= 0.14"
  required_providers {
      google = {
        source  = "hashicorp/google"
        version = "4.37.0"
      }

      google-beta = {
        source  = "hashicorp/google-beta"
        version = "4.37.0"
      }
  }
    backend "gcs" {
      bucket = "msw-terraform-state"
      # Structure:
      # state/<application/<entity>/<environment>/
      prefix = "state/makesmthngwebsite/test/"
    }
}