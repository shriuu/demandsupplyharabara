# Infrastructure (Terraform)

Creates: Artifact Registry, Firestore (native, asia-south1), four empty Secret Manager secrets,
two least-privilege service accounts, Workload Identity Federation for GitHub Actions, and one
Cloud Run service that scales to zero.

The project ID and repository name come from a git-ignored `terraform.tfvars`
(copy `terraform.tfvars.example`). The repo is public: keep IDs, emails and secret values out.

## Order of work
1. `terraform init && terraform plan` — read the plan. Nothing is billed by planning.
2. `terraform apply` — only after the owner has seen the plan and said yes.
3. Add secret values by hand (Terraform never sees them):
   ```bash
   printf '%s' "$(openssl rand -hex 32)" | gcloud secrets versions add session-signing-key --data-file=-
   gcloud secrets versions add pin-directory --data-file=pins.json   # {"1234": {"actor_id": "...", "role": "area_manager"}}
   gcloud secrets versions add openai-api-key --data-file=-          # paste, then Ctrl-D
   gcloud secrets versions add data-gov-in-api-key --data-file=-
   ```
   A store manager entry also needs `"store_id"`. Delete `pins.json` afterwards.
4. Re-apply with `-var mount_secrets=true` so the service reads them. Secrets listed in
   `unmounted_secrets` (by default `data-gov-in-api-key`) are left out because a secret with no
   version stops the service from starting. Once you add its value, apply again with
   `-var 'unmounted_secrets=[]'` so the service reads it too; until then live prices show as
   unavailable.
5. Copy `terraform output github_variables` into GitHub repository variables; pushes to
   `main` then deploy automatically.

Firestore needs no seed. Load precomputed output with
`python -m harabhara.api.loader <dir>` (see docs/api.md, Storage).

## Before any plain `terraform apply`

`terraform.tfvars` is git-ignored, so the settings that match the live service live only on the
machine that applied them. If the file lacks `mount_secrets = true` and `daily_job_enabled = true`,
`terraform plan` shows the secrets (including `HARABHARA_PIN_DIRECTORY`) removed from the service and
the daily job destroyed. Read the plan first; it should show no secret or job change. Moving state
to a shared bucket would remove this trap (see `docs/handover.md`).
