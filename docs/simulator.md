# Stock simulator: proof against history

Code: `harabhara/sim/simulator.py` (uses `harabhara/state/projection.py`).
Scripts: `scripts/ledger_calibration.py`. Test: `tests/model/test_simulator.py`.

CLAUDE.md s10: feed the simulator the managers' real deliveries and check it reproduces their
real waste and empty shelves before trusting any replay.

## How it works
Each morning the real delivery arrives as one lot. Shoppers buy the freshest stock first
(brief s2). Demand is the corrected demand (sold-out days estimated). At close, stock past its
last sellable day is binned. Lot ages are not in the pack, so each lot starts with the playbook
shelf life for its product.

## Which arrival-life assumption reproduces history (training period only)
| Lot life at arrival | Waste sim (actual 8.00%) | Stock-outs sim (actual 9.38%) | Daily waste correlation |
|---|---|---|---|
| **Grade A rule** | **8.17%** | 10.44% | **0.74** |
| Grade B rule | 9.89% | 15.94% | 0.27 |
| Grade C rule | 11.21% | 21.07% | 0.22 |
| Grade A rule + 1 day | 7.82% | 8.69% | 0.35 |

The grade A rule is used: it matches the level and, unlike the others, the day-to-day pattern.

## By slice (grade A rule, usable training rows)
| | Waste actual / sim | Stock-outs actual / sim |
|---|---|---|
| Fruits | 6.41% / 6.45% | 12.20% / 12.58% |
| Vegetables | 4.64% / 4.67% | 9.44% / 9.92% |
| Leafy greens | 15.27% / 15.79% | **4.24% / 8.19%** |
| Walk-in stores | 8.47% / 8.65% | 8.27% / 9.36% |
| Dark stores | 6.93% / 7.09% | 11.61% / 12.58% |

## Tolerance and what it means
- **Waste:** within 0.5 point overall and 1 point per category (tested). Replay waste results are
  trustworthy.
- **Stock-outs:** within about 1 point overall, but **leafy greens are twice too high** (8.2% vs
  4.2%). Two-day produce is very sensitive to the exact age of stock, which the pack does not
  record. For greens, report only the *change* against the simulated baseline, never the level.
- Daily waste correlation is 0.74, not 1.0: the simulator reproduces the pattern, not each day.

## Assumptions the replay inherits (owner question 13)
- Demand does not change with how much stock is on the shelf or with markdowns beyond what the
  recorded sales already include.
- Lot ages are assumed (grade A shelf life, freshest sold first), not observed.
- Transfers between stores and surplus-buyer sales are not in the base simulator; they are added
  as separate steps with their own rules.
