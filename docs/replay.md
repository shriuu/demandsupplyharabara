# Replay: the same supply, split and ordered differently

Code: `harabhara/sim/replay.py`, `harabhara/decisions/` (`economics.py`, `order.py`,
`allocation.py`). Script: `scripts/replay_report.py`. Tests: `tests/model/test_replay.py`,
`tests/model/test_order_allocation.py`.

**Status: development window only.** Window 10 June to 5 August 2026 (inside the training
period; the forecast was fit on data up to 9 June). The calendar's holdout has NOT been read.
The service-level setting below was tuned on this window, so these numbers are optimistic until
the single holdout run.

## What is compared
All three scenarios use the same days, the same corrected demand, and the simulator proven in
`docs/simulator.md`.
1. **Managers' split (simulated):** each store gets what it actually received.
2. **Same supply, our split:** the total delivered to all stores that day is unchanged (the
   purchase is committed). Only the split across stores changes: each unit goes where the next
   unit is worth most (see `allocation.py`).
3. **Our split, spot buying trimmed:** the total follows the stores' asks, but never falls below
   the committed farmer-group volume. Only mandi spot buying can shrink, and only as a
   suggestion to the DC buying lead.

Fidelity of the baseline in this window: simulated waste 7.77% and stock-outs 10.49%, against
recorded 7.62% and 9.63%.

## Result 1: reallocating the committed supply (farmer volume untouched)
| | Waste | Stock-outs | Lost units | Gross margin |
|---|---|---|---|---|
| Managers' split | 7.77% | 10.49% | 14,859 | 36.05% |
| Our split, same supply | **7.33%** | **9.01%** | **11,089** | **36.30%** |

Waste and stock-outs both fall, in every category (waste -0.4 to -0.7 points; stock-outs -0.9 to
-3.8). By store type it is a trade between shop kinds: dark stores' stock-outs fall 4.2 points
but their waste rises 1.1 points; walk-in stores' waste falls 1.1 points.

## Result 2: also trimming spot (mandi) buying
The order covers demand up to a stated share of outcomes (the service-level floor). A pure cost
balance chose about 70% and produced 24% stock-outs (waste 1.5%), the trade the brief forbids,
because the basket allowance is unset and counts as zero. So a floor is imposed:

| Floor | Waste | Stock-outs | Leafy-greens stock-outs | Margin | Spot trimmed |
|---|---|---|---|---|---|
| managers (simulated) | 7.77% | 10.49% | 8.95% | 36.05% | - |
| 0.90 | 4.03% | 11.10% | 11.95% | 38.18% | 4.1% |
| 0.91 | 4.59% | 9.34% | 10.05% | 37.82% | 3.2% |
| 0.92 | 5.26% | 7.86% | 8.41% | 37.40% | 2.2% |
| **0.925 (chosen)** | **5.62%** | **7.03%** | **7.49%** | **37.17%** | **1.7%** |
| 0.93 | 6.02% | 6.35% | 6.65% | 36.90% | 1.1% |
| 0.95 | 8.06% | 3.57% | 3.44% | 35.54% | -1.7% |
| 0.97 | 11.19% | 1.68% | 1.32% | 33.35% | -5.9% |

0.925 is the lowest waste at which every group's stock-outs stay clearly below the managers'
(leafy greens 1.5 points better; at 0.92 they would be only 0.5 better). It was chosen on the
safer side, not to hit a target: waste at 5.62% is just above the brief's 5.5%.

Farmer groups: the committed volume was delivered in full on every product-day (0 days short).
The farmer-group share of the supply rises slightly when spot buying is trimmed (31.0% to about
32%) because only spot buying shrinks.

## Limits
- The window is in the training period and the floor was tuned on it. Treat as indicative.
- Demand is the corrected demand and does not react to how much is on the shelf (owner question 13).
- Lot ages are assumed (grade A shelf life); leafy-greens stock-out levels are unreliable
  (docs/simulator.md), so read greens as changes.
- The basket allowance is unset (zero). Setting it would raise the cost of empty shelves and
  likely the floor.
- Weather in the forecast is the observed value, not a forecast.
- Transfers, markdowns and surplus-buyer sales are not in this replay; they would reduce waste
  further. Held-back surplus under trimming is not modelled.
