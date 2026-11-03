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
  description = "Set true only after a version has been added to every secret that is mounted (see unmounted_secrets)."
  type        = bool
  default     = false
}

variable "unmounted_secrets" {
  description = "Secrets left out of the container until they have a version. A secret with no version stops the service from starting, so add it here until you have its value."
  type        = list(string)
  default     = ["data-gov-in-api-key"]
}
