# The daily job

Code: `harabhara/jobs/daily.py`. Infrastructure: `infra/terraform/daily_job.tf` (off by default).
Run by hand: `HARABHARA_DATA_DIR=work uv run python -m harabhara.jobs.daily` (needs Google sign-in and the project set).

## What it does
Once a day, before the evening ordering window opens, it fits the model for one data day, builds
every suggestion, forecast, scorecard and farmer estimate, and loads them into Firestore so the
four screens have fresh content. It uses the same code as `pipeline.run --demo-today` and the
same loader.

## What it does not do (read this)
The data pack ends on 5 August 2026 and the real date is November, so this job **cycles through
28 past data days** and shows one of them as "today". It keeps the demo alive. It is **not** a live
feed. For real operations the next owner replaces the data pack with a daily feed of sales, stock
and deliveries. The window length is `modeling.pipeline.daily_demo_window_days` (assumed).

## Safe to repeat
The same calendar day always picks the same data day and the same suggestion ids, and the loader
skips ids it already holds. Running it twice created 363 suggestions the first time and 0 the
second (checked locally, about 3.5 minutes per run on 4 CPUs). A decision a manager has made is
never undone. The job never reads the holdout: the data day is always inside the training period
(property test in `tests/backend/test_daily_job.py`).

## What turning it on creates
A private bucket for the data pack, a Cloud Run job (4 CPU, 8 GiB, 30 minute limit), a scheduler
entry (default 19:30 IST), and three service accounts with only what each needs: the job reads the
bucket and writes Firestore; the scheduler may start the job; the deploy account keeps the job on
the newest image. Cost is a few minutes of compute a day plus a small bucket.

## Steps to turn it on (owner decides; none is done yet)
1. `daily_job_enabled = true` in `terraform.tfvars`, then `terraform plan` and `apply`.
2. Upload the data pack (synthetic) to the bucket named in `terraform output daily_job`.
3. Set the GitHub variable `CLOUD_RUN_DAILY_JOB` to the job name so deploys update it.
4. Start it once by hand in the Cloud Run console and check the screens, then leave it on the schedule.
