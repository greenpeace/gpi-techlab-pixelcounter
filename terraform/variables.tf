variable "entity" {
  type = string
  default = "pixelcounter-test"
}
variable "environment" {
  type = string
  default = "test"
}
variable "gcp_region" {
  type = string
  default = "europe-north1"
}
variable "image_name" {
  type = string
  default = "pixelcounter-test"
}
variable "project_id" {
  type = string
  default = "make-smthng-website"
}

variable "repository" {
  description = "The name of the Artifact Registry repository to be created"
  type        = string
  default     = "pixelcounter-test"
}

variable "docker_image" {
  description = "The name of the Docker image in the Artifact Registry repository to be deployed to Cloud Run"
  type        = string
  default     = "gpipixelcounter-test"
}
