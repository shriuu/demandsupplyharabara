# Shelf-life model

Code: `harabhara/models/shelf_life.py`. Settings: `config/modeling.yaml` (`shelf_life`).
Report: `scripts/shelf_life_report.py` (aggregates only).

## What it does
Estimates remaining sellable days for a lot from what QC measures on arrival: age since
harvest, receipt temperature, firmness, colour, visible defects, assigned grade, source and
product. Three CatBoost models (10th, 50th, 90th percentile) give a low, likely and high
estimate. The result is **capped at the playbook rule**, reduced by a day for arrivals warmer
than the limit (guardrail G06). The rule and the model are both returned.

## Weather is not a feature, on purpose
Tested on the 3,867 QC samples joined to Bengaluru weather by date:
- Ambient humidity, maximum temperature and rainfall have effects near zero, including for
  leafy greens, and adding them changes held-out error by 0.00 to 0.01 days.
- Receipt temperature is not related to that day's weather in this pack either.
- Arrival temperature does matter: above the limit, life is shorter than the rule by about
  0.4 to 0.7 extra days (greens -0.72 vs -0.24, vegetables -0.98 vs -0.32, fruit -0.81 vs -0.36).
The pack cannot show a humidity effect, so none is built in. If the owner states one (for
example "humidity above X cuts leafy greens by a day"), it goes in `config/` as an
owner-sourced rule and shows in the reason, but it cannot be validated on this data.

## Results on QC samples the model never saw
Fit on samples dated up to 31 May 2026; scored on 1 June to 5 August 2026 (647 samples). QC
samples dated in the holdout (6 Aug onwards) have not been read.

| Estimator | MAE (days) | Bias (days) |
|---|---|---|
| Fixed rule | 0.85 | +0.38 |
| Rule with warm-arrival penalty | 0.83 | +0.24 |
| Model, no rule cap (for comparison) | 0.59 | +0.06 |
| **Model, capped by the rule (what ships)** | **0.62** | -0.24 |
| Model, whole days rounded down (what the ledger plans with) | 0.68 | -0.54 |

| Category | n | Rule MAE | Model MAE |
|---|---|---|---|
| Fruits | 214 | 0.85 | 0.68 |
| Leafy greens | 97 | 0.67 | 0.46 |
| Vegetables | 336 | 0.87 | 0.63 |

Warm arrivals: rule 0.87, model 0.78. Other arrivals: rule 0.83, model 0.60.

**T09** (tomato, 2 days since harvest, 31 C, firmness 5.8, grade B): fixed rule 4 days, rule with
warm penalty 3, model about 2.7 (range 1.8 to 3.0). Below the rule, as the brief expects.

## Where it loses or is uncertain
- **The cap costs accuracy.** Observed life exceeds the capped rule on 25% of samples, and the
  model wants to go above it on 43%. The cap trades 0.03 days of error and turns a small
  over-estimate into a under-estimate (bias -0.24). That is the price of guardrail G06; whether
  it should hold when QC shows longer life is open owner question 14.
- **The range is not calibrated.** Uncapped, the 10-90 range holds 95% of outcomes (too wide).
  After the cap it holds 71%, because the cap clips the upper end below what was observed.
  A calibration step is still to do.
- **Rounding down is conservative.** Whole days planned with are 0.54 days below the observed
  life on average, which will mark some produce as "won't last" a little early. Leftover risk is
  slightly overstated; the cost is some discounts that start a day early.
- Settings were chosen on validation samples inside the training period (300 iterations
  under-fitted; 1500 chosen). Treat the validation numbers as mildly optimistic until the one
  final holdout run.
- Only 647 validation samples; per-product results are too thin to quote.
