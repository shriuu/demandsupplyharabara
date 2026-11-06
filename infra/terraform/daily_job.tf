# ---- Scheduled daily job (off unless daily_job_enabled) ----------------------------------
# Runs `python -m harabhara.jobs.daily` from the same image as the service: fits the model for
# one data day, writes the suggestions and loads them into Firestore. The data pack is read
# from a private bucket mounted at /data; it is uploaded by hand (see docs/daily_job.md).

locals {
  daily = var.daily_job_enabled ? toset(["on"]) : toset([])
}

resource "google_project_service" "scheduler" {
  for_each           = local.daily
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "pack" {
  for_each                    = local.daily
  name                        = "${var.project_id}-${var.service_name}-pack"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# The job runs as its own account: Firestore and the data bucket, nothing else.
resource "google_service_account" "daily" {
  for_each     = local.daily
  account_id   = "${var.service_name}-daily"
  display_name = "HaraBhara daily job"
}

resource "google_project_iam_member" "daily_firestore" {
  for_each = local.daily
  project  = var.project_id
  role     = "roles/datastore.user"
  member   = "serviceAccount:${google_service_account.daily["on"].email}"
}

resource "google_storage_bucket_iam_member" "daily_reads_pack" {
  for_each = local.daily
  bucket   = google_storage_bucket.pack["on"].name
  role     = "roles/storage.objectViewer"
  member   = "serviceAccount:${google_service_account.daily["on"].email}"
}

resource "google_cloud_run_v2_job" "daily" {
  for_each            = local.daily
  name                = "${var.service_name}-daily"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.daily["on"].email
      timeout         = "1800s"
      max_retries     = 1

      containers {
        image   = var.image
        command = ["python", "-m", "harabhara.jobs.daily"]

        resources {
          limits = {
            cpu    = "4"
            memory = "8Gi"
          }
        }

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "HARABHARA_DATA_DIR"
          value = "/data"
        }
        volume_mounts {
          name       = "pack"
          mount_path = "/data"
        }
      }

      volumes {
        name = "pack"
        gcs {
          bucket    = google_storage_bucket.pack["on"].name
          read_only = true
        }
      }
    }
  }

  # GitHub Actions rolls out new images; Terraform must not roll them back
  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.apis, google_storage_bucket_iam_member.daily_reads_pack]
}

# The scheduler calls the Cloud Run API to start the job.
resource "google_service_account" "scheduler" {
  for_each     = local.daily
  account_id   = "${var.service_name}-scheduler"
  display_name = "HaraBhara scheduler"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_job" {
  for_each = local.daily
  location = var.region
  name     = google_cloud_run_v2_job.daily["on"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler["on"].email}"
}

resource "google_cloud_scheduler_job" "daily" {
  for_each  = local.daily
  name      = "${var.service_name}-daily"
  region    = var.region
  schedule  = var.daily_job_schedule
  time_zone = var.daily_job_timezone

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.daily["on"].name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler["on"].email
    }
  }

  depends_on = [google_project_service.scheduler]
}

# The deploy account keeps the job on the newest image.
resource "google_cloud_run_v2_job_iam_member" "deploy_job" {
  for_each = local.daily
  location = var.region
  name     = google_cloud_run_v2_job.daily["on"].name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_acts_as_daily" {
  for_each           = local.daily
  service_account_id = google_service_account.daily["on"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}
