# Business case and pilot plan

Numbers come from `docs/final_results.md` (the calendar holdout, 6 Aug to 30 Sep 2026, read once).
Where a figure is not in that file, it is not here.

## What the replay shows
| | Waste | Empty shelves | Gross margin | Farmer-group share of supply |
|---|---|---|---|---|
| Managers' split (simulated) | 9.46% | 8.68% | 35.63% | 31.8% |
| Our split, spot buying trimmed | 5.76% | 6.00% | 37.47% | 32.9% |

- Waste falls by 3.7 points and empty shelves by 2.7 points, so the two did not trade against each other.
- Gross margin rises by 1.8 points. Confirmed farmer-group volume was never cut.
- Forecast error is 19.5% against the managers' 23.6% on the same rows.

## How far to trust it
- The replay assumes demand does not respond to extra stock or to markdowns, and it uses one data pack.
- The service floor of 0.925 was tuned on training data, not the holdout.
- Leafy greens gain least on empty shelves (0.26 points).
- Festival lift is under-forecast for bananas and coconut (1.16x against 1.29x for Robusta banana).
- The value of a lost sale is a placeholder until the owner sets it (owner question 5). Margin is
  gross margin on this data, not a profit figure the finance team has signed off.
- Supply split and spot trimming are advice for the DC buying lead. Nothing is bought or cut by the tool.

## Pilot plan
1. **Shadow mode (2 weeks).** Run the pipeline each evening, hide suggestions, record what managers
   order. Compare ours with theirs on waste, empty shelves and farmer share. Not built yet; it needs
   a hidden flag on suggestions and a daily schedule (see `docs/handover.md`).
2. **Suggest mode in a few stores (4 weeks).** Pick stores of both types (walk-in and dark) and keep
   comparison stores with similar sales. Managers tick, edit with a reason, or reject.
3. **Decide.** Continue only if, against the comparison stores, waste is lower and empty shelves and
   farmer share are not worse, reported together. Playbook section 10 allows automatic ordering only
   after beating managers for the pilot period; until then a person approves.

## What the pilot must measure
- Acceptance rate of suggestions and the reasons given for edits and rejections.
- Waste, empty shelves and farmer share per store and category, weekly.
- Deadlines missed (suggestions that expired).
- Whether managers who cannot read the interface language can finish the evening order unaided.

## Decisions needed before the pilot
Lost-sale value, what counts as waste, what happens if a manager misses the deadline, who approves when
the area manager is away, how farmer share is defined, and the recall procedure
(`docs/owner_questions.md`).
