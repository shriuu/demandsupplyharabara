variable "project_id" {
  description = "GCP project ID. Supply it in a git-ignored terraform.tfvars; it is not kept in the repo."
  type        = string
}

variable "region" {
  type    = string
  default = "asia-south1"
}

variable "github_repository" {
  description = "owner/name of the GitHub repository allowed to deploy (Workload Identity Federation)."
  type        = string
}

variable "service_name" {
  type    = string
  default = "harabhara"
}

variable "image" {
  description = "Container image. The default is Google's hello image so the first apply works before any build."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "allow_public" {
  description = "Let anyone open the web address (the app itself signs people in with a PIN)."
  type        = bool
  default     = true
}

variable "mount_secrets" {
  description = "Set true only after a version has been added to every secret in secret_env."
  type        = bool
  default     = false
}
