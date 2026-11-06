# Handover guide

For the person who takes over HaraBhara Fresh. Plain steps; commands are copy-and-paste.
All data is synthetic. The problem owner's data pack is not in this repository.

## 1. First, three things that stop the site
1. **Billing.** The cloud project runs on trial credit that **ends 28 January 2027**. Before then,
   attach your own billing account to the Google Cloud project or the site stops.
2. **Secrets.** Four secrets live in Google Secret Manager (values are never in the repo):
   `pin-directory` (who can sign in, and as which role), `session-signing-key`,
   `openai-api-key` (the chat assistant), `data-gov-in-api-key` (mandi prices; none exists yet).
3. **Sign-in PINs.** Change them by editing `pin-directory` in Secret Manager. Do not paste PINs
   or keys into chat, issues or commits.

## 2. What runs where
| Part | Where |
|---|---|
| Web app and API | One Cloud Run service, Mumbai region |
| Data (suggestions, forecasts, approvals, audit log) | Firestore |
| Deploys | GitHub Actions on every merge to `main` (needs green CI) |
| Infrastructure | Terraform in `infra/terraform` |

## 3. The daily rhythm
The tool does not run itself on a schedule until the daily job is turned on (`docs/daily_job.md`). A day's suggestions are produced by one command,
then loaded:
```bash
uv run python -m harabhara.pipeline.run --work work --out artifacts/run --as-of YYYY-MM-DD
GOOGLE_CLOUD_PROJECT=<project> uv run python -m harabhara.api.loader artifacts/run
```
`work/` holds a copy of the data pack. Use `--demo-today` to show a past day as today (demo only).
The loader never overwrites a suggestion that already exists. **Scheduling this job is the next
piece of work**; see section 6.

## 4. Safety controls
- **Kill switch:** the area manager's screen has "Stop all suggestions". While on, nothing new is
  shown, decisions are refused, and stores carry on the usual way.
- **Nothing acts alone.** Orders, discounts and transfers need a person's tick. The service
  refuses to start if config allows automatic action.
- **Audit log:** every suggestion, edit, reason and decision is recorded. The area manager can read it.

## 5. Where the rules live
`config/*.yaml` holds every limit (discount steps, van cost, deadlines, cost weights). A value
the playbook does not give is empty and marked "source: OWNER". `docs/traceability.yaml` maps each
rule to its code and test. Changing a limit means editing config and passing the tests.

## 6. Not done, in order of importance
1. **Use the recorded outcomes** (`docs/outcomes.md`): stores and the DC now record what happened, but nothing reads it back into forecasts or scorecards yet.
2. **Turn on the daily schedule.** The code and Terraform are written and checked but off: see `docs/daily_job.md`. It cycles past demo days; a real daily data feed is still needed for live use.
2. **Owner decisions** in `docs/owner_questions.md`: value of a lost sale, what counts as waste,
   what happens if a manager misses the deadline, how farmer share is defined, recall procedure.
3. **A weather forecast source.** The model uses observed weather standing in for a forecast.
4. **A mandi price feed.** The DC page shows "no prices" until a data.gov.in key is added.
5. **Store distances.** Transfers are not checked against the 6 km limit; the pack has no coordinates.
6. **Weekly retrain** with drift checks, and a model registry.
7. **Voice, translations, offline mode** and a usability test with people who cannot read the interface language.
8. **Shadow mode** before suggest mode, then a pilot with comparison stores.
9. Terraform state is on one laptop; move it to a storage bucket.

## 7. If something breaks
| Sign | Check |
|---|---|
| Sign-in says "not ready" | `pin-directory` or `session-signing-key` is empty or missing |
| Screens show "nothing" | The day's run was not loaded, or its forecasts are for another date |
| Suggestions missing | Kill switch is on, or the deadline passed (they expire; nothing happens) |
| Deploy fails | GitHub Actions log; CI must be green on `main` |

## 8. Read these first
`CLAUDE.md` (rules and scope), `docs/plan.md` (status), `docs/decisions.md` (why),
`docs/roles.md` (who does what), `docs/final_results.md` (holdout results, once run).
