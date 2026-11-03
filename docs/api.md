# API outline (contract for the parallel workstreams)

Types live in `harabhara/contracts.py`. JSON field names equal the Python names. The API is the
only way the screens, the assistant and the jobs see data. Names are final for the 12 November
release; changes need a pull request that also updates `tests/test_contracts.py`.

Base path `/api/v1`. All times are `Asia/Kolkata`. Every response carries `data_snapshot_id`,
`model_version` and `config_digest` where it holds model output.

| Method and path | Roles | Returns / does |
|---|---|---|
| `GET /health` | none | `{status, kill_switch}` |
| `POST /admin/kill-switch` | area_manager | Stops new suggestions; manual process carries on (guardrail 12) |
| `GET /forecasts?store_id&sku_id&date` | store_manager, dc_lead | `list[Forecast]` |
| `GET /projections?store_id&sku_id` | store_manager, area_manager, dc_lead | `list[Projection]`: three-day stock roll-forward as ranges (sold, lost sales, expected waste, closing stock) |
| `GET /suggestions?role&store_id&kind&state` | any (scoped) | `list[Suggestion]`, most urgent first |
| `GET /suggestions/{id}` | any (scoped) | `Suggestion` with drivers |
| `POST /suggestions/{id}/decision` | the suggestion's `approver_role` | body `Approval`; moves state; writes an `AuditEvent` |
| `GET /dc/totals?date` | dc_lead | per-product totals with `Range`, plus spot-first trimming suggestions |
| `GET /prices?sku_id` | dc_lead | `list[PriceQuote]` incl. a price-shock flag |
| `GET /farmers/forecast?fpo_id` | farmer_coordinator | `list[FarmerVolumeForecast]`, always labelled "estimate" |
| `GET /scorecard?scope` | area_manager | `list[Scorecard]`; waste, stock-outs and farmer share always together |
| `POST /assistant/ask` | any (scoped) | body `{suggestion_id, question}`; answers only from that suggestion's stored trail |
| `GET /audit?suggestion_id` | area_manager | `list[AuditEvent]` (read only) |

## Rules every endpoint follows
- **Approval is the only way state changes.** Nothing orders, reprices or moves stock.
- **Role scoping:** a store manager sees only their store. A role can't call another role's
  endpoints.
- **Failure:** if data or a model is stale, return it marked stale, or return less. Never
  guess (guardrail 12).
- **Assistant:** reads one stored `Suggestion` and its `drivers`; it can reword, never decide.
  Unknown questions get "I don't have that."
- **Prices:** `PriceQuote.status = unavailable` carries no price.

## Storage
Firestore collections: `suggestions`, `approvals`, `audit` (create-only), `prices`,
`forecasts`. Precomputed forecasts and suggestions are loaded by the nightly job.

## Draft screens by role
| Role | Screens |
|---|---|
| store_manager | Tonight's orders; morning alerts; surplus plan to confirm |
| area_manager | Approvals queue; store scoreboard (waste, stock-outs, farmer share) |
| dc_lead | Totals with ranges; price warnings; spot-first trimming view |
| farmer_coordinator | Three-day volumes per product, labelled "estimate" |
