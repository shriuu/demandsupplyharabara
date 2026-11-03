# ADR-0005: 12 November release, storage and assistant

Status: **Accepted** (2026-11-03). Replaces the database choice in ADR-0002.

## Context
Go-live is 12 November 2026, followed by a handover. The owner requires the four role screens,
markdown timing, a chat assistant and live mandi prices. The GCP trial credit ends 28 January.

## Decision
1. **Storage:** Firestore for suggestions, approvals, the append-only audit log, prices and
   precomputed forecasts. No idle cost, nothing to manage. Postgres/Cloud SQL is deferred.
2. **One Cloud Run service** serves the API and the built web app; it scales to zero.
3. **Forecasts and suggestions are precomputed** by a pipeline and loaded into Firestore.
4. **Assistant:** OpenAI behind a provider-neutral interface; the model name is configuration.
   It reads one stored suggestion and rewords its drivers; it cannot create or change
   anything. The key lives in Secret Manager, never in the repo.
5. **Mandi prices:** live government feed shown with its citation. The demand model keeps
   training on the pack's synthetic prices; mixing real prices into synthetic history would
   break the link between price and sales.
6. **Markdown timing** chooses among the existing steps only. The price response is estimated
   from the 15% promotion rows and labelled an assumption. Starting before the last sellable
   day is a suggestion that needs approval (owner question 8, assumed yes).

## Deferred, with a written plan for the next owner
Voice, translations, offline mode, the 5-person usability study, a dev/staging/prod split.

## Consequences
- The next owner must attach their own billing to the project before 28 January.
- Firestore's document model means no SQL reporting; the scorecard is computed by the jobs.
