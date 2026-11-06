# Recording what really happened

Until now the tool only recorded decisions. It could not say what was actually bought, sold or
thrown away after a decision. Two screens now do that. Both are **records only**: nothing is
ordered, priced or moved.

| Who | Where | What is recorded | Endpoint |
|---|---|---|---|
| Store manager | "Closing" tab, one tile per approved or edited order | Units sold, units thrown away, ran out or not | `POST /api/v1/outcomes` (kind `closing`) |
| DC buying lead | "What you bought today" | Units bought from farmer groups and from the mandi, per product | `POST /api/v1/outcomes` (kind `purchase`) |

## Rules (tested in `tests/backend/test_outcomes.py`)
- A store manager records only their own store; only the DC lead records purchases. Others get 403.
- A day that has not happened yet is refused. Who and when come from the sign-in and server clock.
- One record per day, store, product and source. Saving again replaces it, and **every submission
  is a new audit event** (`type: outcome`), so the first entry stays in the history.
- Closing an approved or edited order marks that suggestion `done` (the state the approval
  machine already reserved). A proposed order or another store's is never touched.
- Recording keeps working while the kill switch is on: it states a fact, not a suggestion.

## Not done yet
- Nothing reads these records back. The forecast, the scorecards and farmer share still come from
  the data pack. Feeding outcomes into the next forecast and the scorecards is the next step.
- No screen lists past records, and there is no edit or delete beyond saving again.
- The step size for entering units (`ENTRY_STEP_UNITS`) is a screen setting, not a business rule.
