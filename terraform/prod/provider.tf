# Configure GCP project
provider "google-beta" {
  project     = var.project_id
  region      = var.gcp_region
}
