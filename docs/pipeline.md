# The pipeline: from the data pack to what the screens show

Code: `harabhara/pipeline/` (`inputs.py`, `forecast.py`, `run.py`).
Run: `uv run python -m harabhara.pipeline.run --work work --out artifacts/run [--as-of DATE] [--demo-today]`
Load: `python -m harabhara.api.loader artifacts/run` (needs Google sign-in and the project set).

## What one run does, for an as-of day A
1. **Fit** the demand model on data up to **A-1**, after calibrating the forecast range on the
   four weeks before (using a model fit before that window, so the calibration is honest).
2. **Forecast** three days ahead twice: from the evening of A (days A+1 to A+3) and from the
   evening of A-1 (days A to A+2, the "morning view").
3. **Stock**: rebuild what is on every shelf by age, from recorded deliveries (grade A shelf life,
   freshest sold first). Shelves at A-1 close plus A's delivery give the morning view; shelves at
   A's close give the evening view.
4. **Evening orders for A+1**: one per store and product: the ask from the demand range and
   stock, with a range, the managers' recorded order beside it, drivers and a one-sentence reason.
5. **Morning alerts for A**: per product across stores: transfers first, then markdowns, then
   surplus offers to buyers. Shortage and surplus use the **expected** outcome (Swanson's rule over
   the low, likely and high cases), not the likely case alone, which hides tail risk.
6. **Guardrail engine** filters everything. Blocked suggestions are listed in `blocked.json`,
   never shown.
7. **Other outputs**: forecasts, three-day projections, farmer-group volume estimates (always
   "estimate"), scorecards (waste, stock-outs and farmer share together), and spot-first
   trimming advice for the DC lead.

## What it reads, and what it does not
- Only data dated up to A is used. No sales, stock or waste after A is read, and the model is
  fit on data up to A-1.
- For days after A it reads only the **calendar** and **weather** (and whether a product is in
  season), which are known in advance. The weather is the observed value, standing in for a
  forecast.
- **The holdout is not read for outcomes.** The command refuses an as-of day inside the holdout.
  The holdout is scored once, on 11 November.

## Demo-day mapping (`--demo-today`)
Real time is November 2026 but the data ends in August, so every deadline would already have
passed and the API would expire everything. With `--demo-today`:
- all dates shift so the as-of day is shown as today;
- deadlines are kept at least a few hours ahead;
- ids carry a `@demoYYYYMMDD` tag, so a later load on another day does not collide.
The content (weather, festival, stock, demand) stays that of the data day. This is for the demo
only and is labelled as synthetic data.

## Comparisons shown
- "Managers' order" is the order recorded for the next day on the as-of day. It is not a
  formula: an earlier version computed "recent average minus stock", which understated what
  managers really order and made our asks look 73% too high. The recorded figures are within
  about 2% of our total (11,531 vs 11,284 units on 5 August), with a different split by product.

## Limits
- Lot grades are not in the sales data; surplus offers assume grade B.
- Transfer reach comes from store pairs seen in logged transfers (no coordinates in the pack).
- A transfer must beat the van cost, so on cheap products it rarely does (the playbook's own
  point about small moves).
- Trimming advice uses the managers' recorded total as tomorrow's purchase and the committed
  farmer-group share from recent purchases; farmer volume itself is never reduced.
- Farmer-volume estimates sum store-level ranges, which overstates the spread.
