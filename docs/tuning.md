# Demand model tuning (12 Nov 2026)

Script: `scripts/tune_demand.py`. Training-period data only; the holdout was not read (it was
already read once, so it cannot judge a change). Median forecast only, WAPE against units sold,
ranges not calibrated, so compare rows with each other, not with `docs/final_results.md`.
Windows: A = 10 Jun to 5 Aug 2026, B = 1 Jan to 30 Apr 2026, C = 1 May to 9 Jun 2026 (confirmation
only, not used to choose). Each window is fit only on data before it.

One setting changed at a time (current = 1200 trees, depth 6, rate 0.06):

| Change | Window A | Window B | Mean | vs current |
|---|---|---|---|---|
| current | 19.34% | 20.35% | 19.85% | - |
| depth 4 | 19.31% | 20.25% | 19.78% | -0.07 pts |
| depth 8 | 19.39% | 20.40% | 19.90% | +0.05 pts |
| l2 10 | 19.31% | 20.35% | 19.83% | -0.01 pts |
| l2 30 | 19.35% | 20.28% | 19.82% | -0.03 pts |
| 600 trees, rate 0.12 | 19.43% | 20.47% | 19.95% | +0.10 pts |
| 2400 trees, rate 0.03 | 19.29% | 20.25% | 19.77% | -0.08 pts |
| recent days weigh more (60 d half-life) | 19.40% | 20.37% | 19.88% | +0.04 pts |
| recent days weigh more (180 d half-life) | 19.42% | 20.32% | 19.87% | +0.02 pts |

Combined (2400 trees, depth 4, rate 0.03): A 19.30%, B 20.17%, **C 19.65% vs 19.72%** for current.

## What it says
- Settings are on a plateau: the best combination gains 0.04 to 0.18 points. That is within the
  noise of two windows and one data pack, so **the shipped settings are unchanged**.
- Recency weighting does not help. More trees and a lower rate help slightly but cost about 4x the
  training time for under 0.1 points.
- Further gains will not come from settings. Better inputs (a real weather forecast, hourly sales,
  recorded outcomes) and the owner's basket allowance matter more. Weekly refit (ablation:
  -0.1 to -0.45 points) is the one modelling change with a measured gain.
- Not done: festival-eve per-product effect, range calibration by product group.
