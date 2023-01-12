locals {
  app_name = "pixelcounter"
  services = [
    "iam.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ]
  image = "europe-north1-docker.pkg.dev/${var.project_id}/${var.repository}/${var.docker_image}:v0.4"
  #image = "eu.gcr.io/${var.project_id}/${var.image_name}:v0.2"
}
