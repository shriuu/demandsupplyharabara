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
4. Re-apply with `-var mount_secrets=true` so the service reads them.
5. Copy `terraform output github_variables` into GitHub repository variables; pushes to
   `main` then deploy automatically.

Firestore needs no seed. Load precomputed output with
`python -m harabhara.api.loader <dir>` (see docs/api.md, Storage).
