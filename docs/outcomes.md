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

## What reads the records now
The area manager's screen shows **"What stores recorded"** beside the data-pack scoreboard
(`GET /api/v1/scorecard/recorded`, code in `harabhara/sim/recorded.py`, tests in
`tests/model/test_recorded_scorecard.py`). Waste, empty shelves and farmer share are always
together (guardrail 4), over the scorecard window in `config/modeling.yaml`.
- **Waste** is thrown away out of sold plus thrown away. Units received are not recorded, so this
  is not the same figure as the data-pack one (binned over received); the screen says so.
- **Empty shelves** is the share of closing records marked "ran out".
- **Farmer share** is farmer-group kilos over all kilos the DC recorded, chain-wide only. With no
  purchases recorded it says "not known" and why. It uses the open owner definition (Q16).
- Nothing recorded means no scorecard and a plain notice, never zeros.

## Not done yet
- **Forecasts do not learn from the records.** The demand model trains on the data pack. The
  recorded sold-out flag and units are the right input for the hidden-demand step, but the demo
  cycles past data days, so mixing November records into that history would be wrong. Do this when
  the real daily feed replaces the data pack (the records and the feed should then be one source).
- No screen lists past records, and there is no edit or delete beyond saving again.
- The step size for entering units (`ENTRY_STEP_UNITS`) is a screen setting, not a business rule.

## DC lead: what the stores ordered, and which mandi

- `GET /api/v1/dc/orders` (DC lead only) adds up the newest evening's orders per product. **Confirmed** is what stores approved, or edited to their own amount. **Waiting** is the suggested amount where a store has not decided. Rejected orders add nothing. It is information only: nothing is ordered, changed or reduced from it (guardrails 1, 3).
- Spot purchases now name the mandi: `APMC Yeshwanthpur` or `K.R. Market`, the two the data pack's purchases use (`config/feeds.yaml`, `buying_markets`). Farmer-group purchases name no market. One record per day, product, source and market.
- The mandi price feed (`/prices`) is a separate thing: it says what the market charges. Where the DC bought comes only from what the DC lead records.

## DC lead: where each product goes

Each product on the "What the stores ordered" list opens to "Send to which area and store": the area's total, then each store's confirmed amount (or the suggested amount, marked amber, where the store has not decided; "no order" where it rejected). Areas come from `config/areas.yaml`. Information only: it orders and changes nothing, and it never lowers a confirmed farmer-group volume.

## Last seven days

`GET /api/v1/history/week` (store managers and area managers only). Seven days ending today, store by store.
- **Store manager:** their own store only, with every order line (suggested amount, what was confirmed, or "refused", "ran out of time", "still waiting") and every closing line. Tab "Last 7 days".
- **Area manager:** a summary per store in their area (or all stores if they have no area): thrown away and ran out together, how many days were closed, orders answered against orders that ran out of time, and a seven-day strip. Tapping a store opens its scoreboard.
- **Waste here** is thrown away over sold plus thrown away, from the counts stores enter (units received are not recorded). A day with no closing count shows a dash: unknown, never zero.
- **Farmer share** is chain-wide only, because purchases are not recorded per store; the screen says so. It is shown beside waste and empty shelves (guardrail 4).
- Orders are counted on the day they were made. Orders past their deadline show as "ran out of time", not as answered.
