output "service_url" {
  value = google_cloud_run_v2_service.app.uri
}

# Copy these into GitHub repository variables (see .github/workflows/deploy.yml)
output "github_variables" {
  value = {
    GCP_PROJECT_ID                 = var.project_id
    GCP_REGION                     = var.region
    GCP_WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    GCP_DEPLOY_SERVICE_ACCOUNT     = google_service_account.deploy.email
    GCP_ARTIFACT_REPO              = google_artifact_registry_repository.app.repository_id
    CLOUD_RUN_SERVICE              = google_cloud_run_v2_service.app.name
  }
}

output "daily_job" {
  description = "Set CLOUD_RUN_DAILY_JOB to this in GitHub variables; upload the data pack to the bucket."
  value = var.daily_job_enabled ? {
    job_name    = google_cloud_run_v2_job.daily["on"].name
    pack_bucket = google_storage_bucket.pack["on"].name
  } : null
}
