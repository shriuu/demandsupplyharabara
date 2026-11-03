# CLAUDE.md: HaraBhara Fresh decision tool (PS-10)

Read this file first, every session. It is the project's memory. If something here conflicts with what you were told in chat, ask before acting.

## 1. What we are building

A decision-support tool for a fresh-produce retailer. Each evening it suggests how much each store should order; each morning it flags produce likely to be left over and produce likely to sell out, and suggests a discount, a store-to-store move or a sale to a surplus buyer. A person approves every action. Four kinds of users each get their own very simple screen.

**The goal, in one sentence:** train the forecasting and shelf-life models well enough that the tool cuts waste, and also earns extra profit on days when a product would have sold out, without ever moving risk onto farmers or emptying shelves to hit a waste number.

The tool succeeds only if **waste goes down, empty shelves do not go up, and farmer groups are not worse off**, reported together, always.

## 2. Source of truth (read, never guess)

- The brief (PS-10 problem statement) and the operations playbook. Rules and definitions come from the playbook. If a rule is missing, ask; do not invent it.
- The data pack: sales and stock by day, purchases and quality checks, shelf-life rules, transfers, farmer contracts, surplus buyers, weather, calendar (with the train/holdout split) and mandi prices.
- **The data folder is read-only.** Never edit, move, rename or overwrite anything in it. Copy files into a working directory and work on the copies. Write new outputs to a separate folder.
- **Do not hard-code numbers.** Every limit (discount steps, distances, deadlines, durations, thresholds, targets) lives in `config/` and is sourced from the playbook or the brief. Code reads config. This file contains no numbers on purpose.

## 3. The objective the model serves

Maximise expected profit per store, product and day, subject to the guardrails:

profit = margin on what sells at full price + recovered value from discount and surplus sales − cost of produce wasted − cost of sales lost to empty shelves

- **Waste cost** = purchase cost of units that expire unsold, minus whatever surplus buyers pay.
- **Lost-sale cost** = margin of the missed sale, plus a configurable allowance for the rest of the shopper's basket (the owner decides the value; until then it is a clearly marked placeholder in `config/costs.yaml`).
- **Profit from sold-out days** means recovering sales that would otherwise be lost. We do it five ways, all within scope:
  1. Learn true demand from sold-out days (do not train on the truncated sales).
  2. Do not over-correct after a sold-out day; use the range and the stock age instead of a bigger cushion.
  3. Raise the order range where a lost sale costs more than a wasted unit (the cost ratio decides, per product).
  4. Early sell-out alerts that propose a transfer from a store with surplus.
  5. Keep fast-selling products in stock on the days our forecast says they spike (weekend, festival eve, heat), not on every day.
- Always report **waste, empty shelves and farmer share together**. A change ships only if empty shelves and farmer share did not get worse.

## 4. Scope

### In scope
- Forecast demand for every store and product for the next few days, with a range (low, likely, high).
- Estimate the demand that sold-out days hid.
- Suggest each evening's order with a one-sentence reason. A manager accepts, edits (with a reason) or rejects.
- Morning alerts: likely leftovers (suggest a discount, a transfer or a surplus buyer) and likely sell-outs (suggest a transfer).
- Estimate remaining shelf life per lot from the quality checks; track stock by age.
- A daily surplus plan matched to buyers (notice period, pickup window, grades accepted, capacity).
- A volume forecast per farmer group, shared as information only.
- Different festival boosts by product, not one flat boost.
- Replay history to compare our suggestions with the managers' orders on waste, empty shelves, profit and farmer share.
- Four role-based screens, deployed at a public web address (synthetic data only).

### Out of scope (do not build, do not suggest)
- Changing prices paid to farmer groups, or recommending purchase timing that shifts risk onto farmers.
- Ordering automatically without a manager's approval.
- Dynamic shelf pricing beyond the discounts and promotions already in the data.
- Any product that is not in the data pack.
- Real customer or employee data. All data is synthetic.

## 5. Guardrails (hard rules, enforced by code, never by prompt or model)

These live in the **rules engine** as filters that run after the recommender and before anything reaches a screen. Each has a test that must always pass.

1. **A person approves every order, discount and transfer.** Every edit and its reason is recorded. The system never sends an order, applies a price or moves stock on its own.
2. **Never recommend paying farmer groups below their contract floor**, and never suggest timing purchases to push risk onto them. Better forecasts must cut waste, not shift it upstream.
3. **Never reduce a farmer-group volume that is already confirmed.** When stock is long, trim spot (mandi) buying first, and only as a suggestion to the DC buying lead.
4. **Report waste and empty shelves together, always.** Never show a waste improvement without the empty-shelf result beside it, plus farmer share.
5. **Never route grade C produce to full-price shelves.** It goes to B2B buyers or processing, as the playbook says.
6. **Never suggest selling past the last sellable day.** If the shelf-life model says longer than the playbook rule, the rule wins; show both.
7. **Respect discount, transfer and surplus rules from the playbook** (steps, timing, floors, approvals, distance, van cost, product restrictions, notice periods). All values come from `config/rules.yaml`.
8. **Respect storage rules** (products that must not go in the cold room) and food-safety rules. A recall or safety flag removes the lot from sellable stock immediately.
9. **Every suggestion has a one-sentence reason a store manager would say.** No reason, no suggestion.
10. **Say what is not known.** Show a range, and flag thin history (new season, new store, new product, missing weather, missing price).
11. **Use public data responsibly.** Cite the source and respect the terms of any public price feed. Never invent a price.
12. **Fail safe.** If data, weather, the model or a deadline fails, show less, mark it stale, and let the manager's usual process carry on.

## 6. Constraints on how we work

- **Decision support first.** The tool proposes; people decide.
- **Simple and accurate beats clever.** If two designs are equally accurate, ship the one a store manager can follow.
- **Ranges, not single numbers**, everywhere a forecast appears. The screen may show one recommended number, but the range is stored and used.
- **Explainable.** Reasons come from the real drivers (weather, weekday, festival, stock age, shelf life, a recent sell-out) and the rule that fired, never from free text invented by a model. A language model may only reword a reason that already exists.
- **Replayable.** Each suggestion stores the data snapshot, model version and rule version it used.
- **Audit everything.** Append-only log of suggestions, edits, reasons, approvals and outcomes.
- **Daily clock.** Jobs follow the playbook's daily rhythm: evening ordering window, DC booking, early-morning purchase, morning transfer approval, van cut-off, surplus confirmation, closing record. The times live in `config/schedule.yaml`.

## 7. The problem factors and how each is fixed

| # | Factor (what goes wrong today) | How we fix it | Where it lives |
|---|---|---|---|
| 1 | Sold-out days hide real demand, so history under-reports and the next order is wrong | Estimate the missed demand from the sold-out hour and similar days; train on the estimate; keep a flag for estimated rows | `features/hidden_demand.py` |
| 2 | After a sell-out, managers over-correct with a bigger cushion | Use the calibrated range and stock age, not a flat cushion; show why the order is what it is | `decisions/order.py` |
| 3 | One festival boost is applied to every product | Per-product, per-festival uplift learned from data, pulled toward similar festivals when examples are few | demand model features |
| 4 | Weekends, rain and heat are not planned for | Weather and weekday as model inputs; rain effect separated for walk-in and online-only stores; fall back to seasonal normal when no forecast | demand model + `features/weather.py` |
| 5 | Shelf life is a fixed rule | Shelf-life model on quality-check measurements gives days left per lot, with a range; the playbook rule caps it | `models/shelf_life.py` |
| 6 | Short-life products are over-ordered, and old stock lingers because shoppers pick the freshest | Track stock by age; order against stock that will still be sellable tomorrow; daily "won't last" list | `state/stock_ledger.py` |
| 7 | Leftovers and shortages are handled late and by phone | Morning alerts propose discount, transfer or buyer, in that order of rule fit; approvals tracked with deadlines | `decisions/*`, `workflow/` |
| 8 | Surplus buyers need notice but surplus is found at closing | Predict surplus in advance; plan only where notice and pickup windows can be met | `decisions/surplus.py` |
| 9 | Mandi prices swing and nobody looks at them | Price as a model input; flag price shocks to the DC buying lead; never touch farmer prices | features + DC screen |
| 10 | Risk could be pushed onto farmers when orders shrink | Guardrails 2 and 3, plus farmer-group share as a third reported measure; forecast shared as information only | rules engine, scorecard |
| 11 | Stock records are noisy (duplicates, blanks, outages) | Intake checks: remove duplicates, rebuild blanks from stock arithmetic, detect outages and exclude them from training | `data/validate.py` |
| 12 | Managers do not trust unexplained numbers | One-sentence reasons, edit-with-reason, shadow mode before suggest mode | reason writer, frontend |

## 8. Architecture: options considered and the decision

**Chosen architecture: one global boosted-tree demand model with ranges, a shelf-life model, an age-aware stock ledger, and a rules-based decision layer, all behind an approval workflow.**

| Option | Verdict | Why |
|---|---|---|
| Keep the managers' rule with tweaks | Reject (kept as baseline) | Ignores weather, festivals, price and stock age |
| Per-series statistical models (smoothing, ARIMA) | Baseline only | One model per series cannot share what it learns across stores and products, and handles new items badly |
| **One global gradient-boosted tree model (CatBoost first, LightGBM as challenger) with low, likely and high outputs** | **Chosen** | Uses many drivers at once, shares learning across stores and products, handles categories natively, works on data of this size, fast, explainable; strong record in retail forecasting competitions |
| Deep time-series networks | Challenger only | Needs far more data; harder to explain; try only if trees plateau |
| Pretrained time-series foundation models | Benchmark only | Useful zero-shot check and for thin history; heavier to run and explain |
| Direct "learn the order quantity" (end-to-end or reinforcement learning) | Later, optional | Conflicts with "manager approves with a reason"; start with an explainable order rule |
| Copy a Chinese retailer's system | Copy ideas, not the system | Their stack depends on their own supply chain and on automatic ordering and pricing, which are out of scope here. We adopt: rebuild demand lost in sold-out days, forecast a range, keep simple fallback models, closed loop from outcomes back to forecasts |
| Rules only, no ML | Reject for forecasting; keep for decisions | Rules cannot learn weather, festival or price effects, but rules are exactly right for guardrails and for discount, transfer and surplus limits |

**Decision layer choices**
- Order quantity: an **age-aware newsvendor rule**. Choose the point in the demand range where the cost of one more wasted unit balances the cost of one more lost sale, counting only stock that will still be sellable. Revisit dynamic programming later.
- Discount: choose only among existing discount steps, and decide when to start, using expected leftovers.
- Transfers and surplus matching: small optimisation (assignment or integer programming) under the playbook's limits.

**Components (each has one job)**
1. Data intake and checks
2. Stock ledger (by store, product, lot and age)
3. Feature store (same inputs for training and live use, as of a point in time)
4. Demand model (including the hidden-demand step)
5. Shelf-life model
6. Recommender
7. Rules engine (limits as data; hard filters)
8. Reason writer
9. Approval workflow with deadlines and escalation
10. Audit log
11. API and four screens
12. Monitoring and kill switch
13. Simulator and backtest

## 9. The flow (keep it this simple)

1. **Data in.** Records arrive, are checked, cleaned and stored.
2. **Forecast.** The demand model gives a range per store and product; the shelf-life model gives days left per lot.
3. **Suggest.** The recommender proposes an order, a discount, a move or a buyer.
4. **Check.** The rules engine blocks anything not allowed.
5. **Explain.** The reason writer attaches one sentence.
6. **Decide.** The right person approves, edits (with a reason) or rejects, before the deadline.
7. **Record.** Everything is logged. Outcomes (sold, wasted, sold out) flow back into the next forecast.

**Suggestion states:** proposed, approved, edited, rejected, expired, done. If a deadline passes, the suggestion expires and nothing new happens.

**Who sees what**
- Store manager: tonight's orders, morning alerts, surplus plan to confirm.
- DC buying lead: totals, ranges, price warnings, spot-first trimming view.
- Area manager: approvals queue, store comparison of waste, empty shelves and farmer share.
- Farmer-group coordinator: expected volumes per product, labelled as an estimate, not a commitment.

## 10. Training the models (be specific, no peeking at the future)

### Demand model
1. **Prepare data.** Remove exact duplicates; rebuild blank waste values from stock arithmetic; exclude detected outages (zero sales while stock moves); mark closures and shocks.
2. **Hidden demand step.** For sold-out rows, estimate the demand that was missed using the sold-out hour, same store and product on comparable days, and weekday and weather. Keep `demand_estimated` and a flag so every evaluation uses only honest rows (non-sold-out) as ground truth.
3. **Targets.** Demand for each of the next days ahead (one target per horizon), by store and product.
4. **Features, as of the evening before (point-in-time only):**
   - recent sales and same-weekday history (lags and rolling means, built from corrected demand, not truncated sales)
   - weekday, month start and payday, school holidays
   - festival name, intensity, day-before flag, and the product's festival sensitivity
   - weather: temperature, rain, humidity, heavy-rain flag; rain interacted with store type
   - shelf price, promotion flag, discount flag, mandi modal price and arrivals, recent price change
   - store attributes (type, size, hours, chilled display) and product attributes (category, season, shelf-life group)
   - stock context from the ledger (opening stock by age, recent sell-out flags) built only from the past
   - thin-history flags (days since season start, days since store opened)
5. **Split by time.** Use the calendar's train/holdout split. The holdout is touched exactly once, at the end. Inside training use rolling-origin validation (train up to a date, predict the next window, repeat).
6. **Baselines first.** Managers' rule (rebuild it exactly as the playbook describes) and a seasonal average. Every model must beat them on the same rows.
7. **Primary model.** CatBoost with quantile outputs (low, likely, high). Categories (store, product, festival, weekday, store type) passed natively. Tune a small number of settings on the rolling folds with early stopping. Sample weights may favour recent days.
8. **Calibrate the ranges** on the most recent validation fold so the stated range holds the stated share of outcomes (conformal-style adjustment). Re-check calibration by product group.
9. **Challengers.** LightGBM; a pretrained time-series model as a benchmark; a simple blend. Keep the simplest model that wins on accuracy, bias, range honesty and the replay.
10. **Evaluate by slice**, not just overall: category, store type, each product, weekday, festival eves, rain days, hot days, sold-out days, new-season days. Report forecast miss and bias per slice.
11. **Robustness.** Re-run with weather removed, with noise added to weather (to mimic a real forecast), with the price feed blank, and with thin-history rows.
12. **Freeze and record.** Save the model, features list, data snapshot id, config and metrics in the model registry. Run on the holdout once. Document the result, including where it loses.
13. **Retrain on a schedule** with drift checks (forecast miss, bias, range honesty). If a new model is worse on rolling tests, keep the old one.

### Shelf-life model
- Inputs per lot: days since harvest, receipt temperature, firmness, colour, defects, grade, source, product.
- Target: observed sellable days from the quality checks. Split by date; keep some checks aside.
- Model: boosted trees or regression with a range. Compare against the playbook rule on held-out checks. Never let output exceed the rule's last sellable day; arrival-temperature and storage rules reduce life as the playbook says.
- Output feeds the stock ledger as "days left" per lot.

### Order and discount decision tuning
- The cost ratio (waste cost versus lost-sale cost) is configuration per product. Tune it on the replay, not on the holdout, and only with the owner's agreed cost definitions.
- Replay uses the stock ledger, the shelf-life rules and the discount rules. **First prove the simulator by feeding it the managers' real orders and checking it reproduces their real waste and empty shelves.** Do not trust any replay result until it does.

## 11. Frontend: simple enough for someone who cannot read

Design for a person who may not read, may not be comfortable with numbers, and is busy on a phone in a store. **If a step needs reading, redesign the step.**

**Principles**
- **Pictures, colour and sound first, words last.** Every product shows a real photo or clear icon. Every action is an icon plus colour. Text is optional and short.
- **One decision per screen.** One product, one question, two big buttons. Next product appears after an answer.
- **Counts as things you can see.** Show quantity as a row of crate or bunch icons, filled to the suggested amount, with a lighter "could be less or more" band. Do not rely on digits alone; show digits small beside the icons.
- **Big green tick = accept. Big red cross = reject. Plus and minus pictures to change the amount.** Same place on every screen.
- **Voice.** Every screen can be read aloud in the user's language with one tap, and the manager can say the reason out loud instead of typing it (voice note stored, text transcribed if possible).
- **Reasons as pictures plus one spoken sentence.** For example: a rain-cloud icon with an arrow down for "rain tomorrow, fewer will come"; a festival lamp icon with an arrow up; a clock icon for "this stock will not last". The sentence is read aloud on tap.
- **Traffic lights for status.** Green fine, amber check, red act now. Never rely on colour alone; always pair with an icon and a sound.
- **Local language, with a language switch that is a picture (flag or script sample), not a word.** All text is translatable; no text baked into images.
- **Low-friction access.** Large tap targets, works on an ordinary phone, works with a poor or no connection (queue actions, show clearly when saved), simple sign-in by PIN or picture pattern.
- **Safe by default.** Nothing important happens on a single accidental tap; destructive or large changes ask "are you sure" with picture confirmation.
- **Fewer alerts, ordered by importance.** At most a short list; the most urgent first.
- **Test with real users.** Test with people who cannot read the interface language. Measure whether they complete the evening order without help. Fix what they cannot do.

**Screens**
- **Store manager (evening):** product photo, crates to order, small band for less or more, a rain, festival or clock icon explaining why, tick, cross, plus and minus, mic for a reason.
- **Store manager (morning):** a short list of red and amber items: leftover (discount, move or buyer) and shortage (transfer). Each is one tap to accept.
- **Surplus plan:** buyer's logo or photo, what they take, pickup time shown as a clock icon, one tap to confirm.
- **DC buying lead:** total per product with range, price warnings with an icon, spot-first trimming view.
- **Area manager:** queue of approvals as cards with tick and cross; a small scoreboard of waste, empty shelves and farmer share shown as three gauges.
- **Farmer-group coordinator:** pictorial sheet of expected volumes per product, labelled "estimate"; deliverable by message, voice or printable page.

## 12. Backend

**Stack (proposed, confirm before locking in):** Python for data and ML; CatBoost and LightGBM; FastAPI for the API; a relational database (start simple, scale later); scheduled jobs; a React progressive web app for the screens; pytest, property-based tests and an end-to-end browser test suite.

**Data model (tables):** stores, products, lots, stock_ledger, sales_daily, deliveries, purchases, quality_checks, weather, calendar, prices, farmer_contracts, surplus_buyers, forecasts, recommendations, approvals, audit_log, model_registry, rule_versions, config_versions.

**API (names, not final):** read forecasts and recommendations by role; submit approval, edit (with reason) or rejection; record counts, deliveries and outcomes; health and kill switch.

**Jobs:** nightly pipeline (intake, checks, hidden demand, forecast, recommend, rules, reasons); morning re-forecast and alerts; surplus planner; closing record; weekly retrain with drift checks. Jobs are repeat-safe (running twice does no harm).

**Config:** `config/rules.yaml` (playbook limits), `config/schedule.yaml`, `config/metrics.yaml` (definitions agreed with the owner), `config/costs.yaml` (waste cost, lost-sale cost placeholders). Versioned; pinned per run.

**Failure handling:** every job has a fallback (yesterday's output marked stale, or the simple baseline). A kill switch stops all suggestions and the manual process carries on.

## 13. Testing (all aspects)

| Aspect | What it proves |
|---|---|
| Data tests | Uniqueness, stock arithmetic balances, duplicates and outages handled, no future information in any feature |
| Model tests | Beats the managers' rule on the same rows; by-slice results; ranges honest; robust to missing or noisy weather and price; thin-history behaviour flagged |
| Shelf-life tests | Beats the fixed rule on held-out quality checks; never exceeds the last sellable day |
| Rule tests (property tests) | Never below the farmer floor; never grade C on full-price shelves; never past the last sellable day; discount, transfer and surplus limits always respected; never reduces a confirmed farmer volume |
| Scenario tests | The brief's acceptance scenarios T1 to T10 pass |
| Simulation | Simulator first reproduces real history with the managers' orders; then waste, empty shelves, profit and farmer share by store and category; sensitivity to assumptions |
| Backend tests | Unit, API contract, approval states and deadlines, repeat-safe jobs, audit completeness, failure-injection (job fails, late data, feed down), load |
| Frontend tests | Component and end-to-end flows per role; works on small phones and poor connections; accessibility (voice, contrast, tap size); every screen usable without reading |
| Usability | People who cannot read the interface language complete the evening order unaided; acceptance rate measured as the brief defines |
| Security | Roles and least privilege, public URL protected, rate limits, synthetic data only |
| Pilot | Shadow mode first (suggestions hidden), then suggest mode in a small number of stores with comparison stores |

## 14. Proposed repo layout

```
config/           rules.yaml, schedule.yaml, metrics.yaml, costs.yaml
data/             validate.py, clean.py (reads copies, never the source folder)
features/         hidden_demand.py, weather.py, calendar.py, price.py, build.py
models/           demand.py, shelf_life.py, registry.py, calibrate.py
state/            stock_ledger.py
decisions/        order.py, discount.py, transfer.py, surplus.py, farmer_volumes.py
rules/            engine.py, guardrails.py
reasons/          writer.py, templates/
workflow/         approvals.py, deadlines.py, audit.py
api/              app.py, routes/
sim/              simulator.py, replay.py, scorecard.py
frontend/         pwa/ (screens by role, voice, icons, translations)
tests/            data/, model/, rules/, scenarios/, backend/, frontend/
docs/             decisions.md, edge_cases.md, owner_questions.md
```

## 15. Working agreements for Claude Code

- Do not invent facts or numbers. If a value is needed, read it from `config/` or ask.
- Never modify the source data folder. Work on copies.
- Before writing code, check this file and the rules table. If a request would break a guardrail or scope line, stop and say so.
- Write the test first for every guardrail.
- Keep screens simple; if a design needs reading, simplify it.
- Report waste, empty shelves and farmer share together whenever you report a result.
- State uncertainty and limits honestly in every result. Say where the model loses.
- Log decisions in `docs/decisions.md` with the reason.
- Ask the owner-question list below before building the parts that depend on it.

## 16. Open questions that change the build

1. What happens when a manager does not respond by the ordering deadline?
2. Who approves discounts and transfers when the area manager is absent?
3. Is trimming spot buying before farmer-group buying allowed?
4. What counts as waste (donated, discounted, sold to surplus buyers)?
5. What is one lost sale worth (including the rest of the shopper's basket)?
6. Can stores record lot or arrival age?
7. Where does the weather forecast come from?
8. Can discounts start earlier than the last day, using only the existing steps?
9. How are one-off shocks (strike, flood, supply shortage) reported?
10. How often may the forecast shared with farmer groups change, and how is it labelled?
11. What food-safety or recall procedure should the emergency block follow?
12. Which languages must the screens support, and is voice input acceptable?
13. How will the replay treat demand when more stock is available, response to discounts and swaps between products?

## 17. Plain-language glossary

- **Sold out / empty shelf:** the product ran out before closing.
- **Hidden demand:** shoppers who wanted the product but found none; recorded sales understate it.
- **Range:** low, likely and high expected demand.
- **Lot:** one delivery of one product with one age and grade.
- **Dark store:** online-only store.
- **Farmer group (FPO):** a company owned by farmers that sells their produce together.
- **Floor price:** the minimum we pay a farmer group under contract.
- **Holdout:** the last stretch of history, kept untouched until the final test.
- **Shadow mode:** the tool runs but its suggestions are hidden from users, so we can compare with what they did.
