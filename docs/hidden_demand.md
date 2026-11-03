# Hidden demand on sold-out days

Code: `harabhara/features/hidden_demand.py`. Settings: `config/modeling.yaml`.
Report script: `scripts/hidden_demand_report.py` (aggregates only).

## Method
If a product sold out at hour h, its demand for the whole day is estimated as
`units sold / share of the trading day gone by h`, never below what was sold. Trading hours come
from `config/schedule.yaml` (walk-in stores and dark stores differ). Rows that did not sell out
keep their recorded sales. Every row keeps `demand_estimated`, so evaluation uses only
honest rows as ground truth.

## What the data shows (all in-season rows; the S07 till outage is excluded)
- 9,145 of 100,287 usable rows sold out and were corrected.
- **Hidden units are small overall: 1.9% of units sold.** Fruit 3.1%, vegetables 2.1%, leafy
  greens 0.7%. Weekends 2.9%, weekdays 1.4%.
- On corrected rows the median uplift is 1.15x, the 90th percentile 1.53x.
- Four rows hit the safety bound (sold out within the first tenth of the day); the bound caps
  their uplift at 10x.

## The assumption, and what it costs if wrong
The data has daily totals only, so the pace of sales through the day cannot be observed. The
estimator assumes an even pace. To see the damage, days that did **not** sell out (known true
demand, training split only) were cut off at the real sold-out times and re-estimated, while the
true pace was varied:

| True pace (gamma) | Meaning | Bias | WAPE |
|---|---|---|---|
| 0.6 | much sold early | +9.2% | 9.2% |
| 0.8 | somewhat early | +4.4% | 4.4% |
| 1.0 | even (assumed) | 0.0% | 0.0% |
| 1.25 | somewhat late | -4.9% | 4.9% |
| 1.5 | much sold late | -9.4% | 9.4% |

These errors apply only to the sold-out rows, so a wrong pace moves the *overall* hidden-demand
figure by well under a percentage point of total units. It matters more for individual
fast-selling products on weekends and festival eves, where sell-outs cluster.

## Limits
- The 1.0 pace is an assumption, not a measured value. If the owner can supply hourly sales for
  even one store, gamma can be fitted and this table replaced by a measurement.
- The stress test cannot prove the pace is right; with gamma 1.0 it is circular by design and
  only shows sensitivity.
- The brief measures WAPE against units sold, which is censored. Forecast accuracy will be
  reported both against units sold and, on honest rows, against known demand.
