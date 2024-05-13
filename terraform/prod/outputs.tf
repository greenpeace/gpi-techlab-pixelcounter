## GCP project ID
#
#output "gcp_project_id" {
#  value = data.google_project.working_project.project_id
#}

output "url" {
  value = google_cloud_run_service.pixelcounter.status[0].url
}
