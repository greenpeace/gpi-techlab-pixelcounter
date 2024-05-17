
resource "google_project_service" "enabled_service" {
  for_each = toset(local.services)
  project  = var.project_id
  service  = each.key

  provisioner "local-exec" {
    command = "sleep 60"
  }

  provisioner "local-exec" {
    when    = destroy
    command = "sleep 15"
  }
}

# This is used so there is some time for the activation of the API's to propagate through
# Google Cloud before actually calling them.
resource "time_sleep" "wait_30_seconds" {
  create_duration = "30s"
  depends_on = [
    google_project_service.enabled_service
    ]
}

#############################################
#    Google Artifact Registry Repository    #
#############################################
# Create Artifact Registry Repository for Docker containers
resource "google_artifact_registry_repository" "my_docker_repo" {
  provider = google-beta
  location = var.gcp_region
  repository_id = var.repository
  description = "Editorial portal docker repository"
  format = "DOCKER"
  depends_on = [time_sleep.wait_30_seconds]
}

# Create a service account
resource "google_service_account" "docker_pusher" {
  provider = google-beta
  account_id   = "docker-pusher"
  display_name = "Docker Container Pusher"
  depends_on =[time_sleep.wait_30_seconds]
}

# Give service account permission to push to the Artifact Registry Repository
resource "google_artifact_registry_repository_iam_member" "docker_pusher_iam" {
  provider = google-beta
  location = google_artifact_registry_repository.my_docker_repo.location
  repository =  google_artifact_registry_repository.my_docker_repo.repository_id
  role   = "roles/artifactregistry.writer"
  member = "serviceAccount:${google_service_account.docker_pusher.email}"
  depends_on = [
    google_artifact_registry_repository.my_docker_repo,
    google_service_account.docker_pusher
  ]
}

resource "null_resource" "docker_build" {

triggers = {
always_run = timestamp()

}

provisioner "local-exec" {
    working_dir = path.module
    command     = "docker buildx build --platform linux/amd64 --push -t ${local.image} ../../."
  }
    depends_on =[
    time_sleep.wait_30_seconds,
    google_artifact_registry_repository.my_docker_repo,
    google_service_account.docker_pusher
  ]
}

resource "google_project_service" "cloud_run" {
  service = "iam.googleapis.com"
  disable_dependent_services = true
  disable_on_destroy = false
}

# Deploy image to Cloud Run
resource "google_cloud_run_service" "pixelcounter" {
  provider = google-beta
  name     = "pixelcounter"
  location = var.gcp_region
  #autogenerate_revision_name = true

  template {
    spec {
      containers {
        image = local.image
        ports {
          container_port = 8080
        }
        resources {
            limits = {
              "memory" = "2G"
              "cpu" = "2"
            }
        }
      }
    }
    metadata {
      annotations = {
          "autoscaling.knative.dev/minScale" = "0"
          "autoscaling.knative.dev/maxScale" = "2"
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
  depends_on = [
    null_resource.docker_build,
    google_artifact_registry_repository_iam_member.docker_pusher_iam,
    time_sleep.wait_30_seconds
  ]
}

# Create public access
data "google_iam_policy" "all_users_policy" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

# Enable public access on Cloud Run service
resource "google_cloud_run_service_iam_policy" "all_users_policy" {
  location    = google_cloud_run_service.pixelcounter.location
  project     = google_cloud_run_service.pixelcounter.project
  service     = google_cloud_run_service.pixelcounter.name
  policy_data = data.google_iam_policy.all_users_policy.policy_data
}

# SECRETS
resource "google_secret_manager_secret" "pixelcounter" {
  project   = var.project_id
  secret_id = "pixelcounter_token"

  replication {
    user_managed {
      replicas {
        location = "europe-west1"
      }
      replicas {
        location = "europe-north1"
      }
    }
  }

  labels = {
    app         = local.app_name
    entity      = var.entity
    environment = var.environment
    source      = "pixel_token"
  }
}

resource "google_service_account" "function" {
  account_id   = "${local.app_name}-${var.entity}-${var.environment}"
  display_name = "Pixelcounter Service Account"
  project      = var.project_id
}

