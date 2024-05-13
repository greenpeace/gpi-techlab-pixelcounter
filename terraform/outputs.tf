## GCP project ID
#
output "url" {
  value = google_cloud_run_service.pixelcounter-test.status[0].url
}
