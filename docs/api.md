# API outline (contract for the parallel workstreams)

Types live in `harabhara/contracts.py`. JSON field names equal the Python names. The API is the
only way the screens, the assistant and the jobs see data. Names are final for the 12 November
release; changes need a pull request that also updates `tests/test_contracts.py`.

Base path `/api/v1`. All times are `Asia/Kolkata`. Every response carries `data_snapshot_id`,
`model_version` and `config_digest` where it holds model output.

| Method and path | Roles | Returns / does |
|---|---|---|
| `POST /auth/login` | none | body `{pin}`; returns `{token, role, actor_id, store_id}`. Send `Authorization: Bearer <token>` on every other call. Repeated wrong PINs get 429 |
| `GET /health` | none | `{status, kill_switch}`; `status` is `degraded` (and `kill_switch` true) if storage can't be read |
| `POST /admin/kill-switch` | area_manager | body `{on: bool}`. While on: no new suggestion is loaded, proposed suggestions are hidden, decisions get 423. Manual process carries on (guardrail 12) |
| `GET /forecasts?store_id&sku_id&date` | store_manager, dc_lead | `list[Forecast]` |
| `GET /suggestions?role&store_id&kind&state` | any (scoped) | `list[Suggestion]`, most urgent first |
| `GET /suggestions/{id}` | any (scoped) | `Suggestion` with drivers |
| `POST /suggestions/{id}/decision` | the suggestion's `approver_role` | body `Approval`; returns the `Suggestion` in its new state; writes an `AuditEvent`. `actor_id` and `at` are set by the server from the sign-in and clock. 409 if not `proposed` or past its deadline |
| `GET /dc/totals?date` | dc_lead | `{on, totals: [{sku_id, demand: Range, stores, flags, ...}], trimming, stale}`; `trimming` is empty until the decision layer stores spot-first trimming output |
| `GET /prices?sku_id` | dc_lead | `list[PriceQuote]` incl. a price-shock flag |
| `GET /farmers/forecast?fpo_id` | farmer_coordinator | `list[FarmerVolumeForecast]`, always labelled "estimate" |
| `GET /scorecard?scope` | area_manager | `list[Scorecard]`; waste, stock-outs and farmer share always together |
| `POST /assistant/ask` | any (scoped) | body `{suggestion_id, question}`; returns `{suggestion_id, answer, source}`; answers only from that suggestion's stored trail; `source` is `stored_reason` if the assistant is down |
| `GET /audit?suggestion_id` | area_manager | `list[AuditEvent]` (read only) |

## Rules every endpoint follows
- **Approval is the only way state changes.** Nothing orders, reprices or moves stock.
- **Role scoping:** a store manager sees only their store. A role can't call another role's
  endpoints.
- **Failure:** if data or a model is stale, return it marked stale, or return less. Never
  guess (guardrail 12). List endpoints keep the `list[...]` body and add the response header
  `X-Data-Stale: true|false`. Forecasts for days already past are dropped; if the store or the
  price feed is down the list is empty (or the last stored prices with `status: stale`).
- **Deadlines:** a `proposed` suggestion past its `deadline` becomes `expired`, with one audit
  event, and nothing else happens.
- **Assistant:** reads one stored `Suggestion` and its `drivers`; it can reword, never decide.
  Unknown questions get "I don't have that."
- **Prices:** `PriceQuote.status = unavailable` carries no price.

## Storage
Firestore collections: `suggestions`, `approvals`, `audit` (create-only), `prices`,
`forecasts`, plus `farmer_forecasts`, `scorecards` and `control` (the kill switch).
Precomputed output is loaded by the nightly job (`python -m harabhara.api.loader <dir>` with
`forecasts.json`, `suggestions.json`, `farmer_forecasts.json`, `scorecards.json`, each a JSON
list of the contract type). Loading never overwrites a suggestion that already exists.
`approvals` and `audit` are create-only.

## Draft screens by role
| Role | Screens |
|---|---|
| store_manager | Tonight's orders; morning alerts; surplus plan to confirm |
| area_manager | Approvals queue; store scoreboard (waste, stock-outs, farmer share) |
| dc_lead | Totals with ranges; price warnings; spot-first trimming view |
| farmer_coordinator | Three-day volumes per product, labelled "estimate" |
