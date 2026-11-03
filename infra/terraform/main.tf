locals {
  repo_name = "harabhara"

  # Secrets are created empty. Values are added by hand (see README.md), never by Terraform.
  secrets = [
    "openai-api-key",
    "data-gov-in-api-key",
    "session-signing-key",
    "pin-directory",
  ]

  # secret id -> environment variable in the container
  secret_env = {
    "session-signing-key" = "HARABHARA_SIGNING_KEY"
    "pin-directory"       = "HARABHARA_PIN_DIRECTORY"
    "openai-api-key"      = "OPENAI_API_KEY"
    "data-gov-in-api-key" = "DATA_GOV_IN_API_KEY"
  }

  mounted_secrets = { for id, name in local.secret_env : id => name if !contains(var.unmounted_secrets, id) }
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ---- Artifact Registry ------------------------------------------------------------------

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = local.repo_name
  format        = "DOCKER"
  description   = "HaraBhara Fresh container images"
  depends_on    = [google_project_service.apis]
}

# ---- Firestore --------------------------------------------------------------------------

resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

# ---- Secret Manager (containers only, no values) -----------------------------------------

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.secrets)
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# ---- Service accounts -------------------------------------------------------------------

# Runs the app: reads and writes Firestore, reads its own secrets, nothing else.
resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-run"
  display_name = "HaraBhara Cloud Run runtime"
}

resource "google_project_iam_member" "runtime_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_reads" {
  for_each  = google_secret_manager_secret.secrets
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# Deploys from GitHub Actions: push images, update the one service, act as the runtime account.
resource "google_service_account" "deploy" {
  account_id   = "${var.service_name}-deploy"
  display_name = "HaraBhara GitHub deploy"
}

resource "google_artifact_registry_repository_iam_member" "deploy_push" {
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_cloud_run_v2_service_iam_member" "deploy_service" {
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# ---- Workload Identity Federation (no stored keys) --------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.service_name}-github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # Only this repository, only its main branch, can deploy
  attribute_condition = "assertion.repository == \"${var.github_repository}\" && assertion.ref == \"refs/heads/main\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_impersonates_deploy" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# ---- Cloud Run --------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "app" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0 # scale to zero: no idle cost
      max_instance_count = 3
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      dynamic "env" {
        for_each = var.mount_secrets ? local.mounted_secrets : {}
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  # GitHub Actions rolls out new images; Terraform must not roll them back
  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [
    google_project_service.apis,
    google_firestore_database.default,
    google_secret_manager_secret_iam_member.runtime_reads,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_public ? 1 : 0
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
