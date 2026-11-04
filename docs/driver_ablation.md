# Which inputs matter: driver ablation (4 Nov 2026)

Script: `scripts/driver_ablation.py`. Each input group is removed in turn, the model refit, and
all variants scored on the same rows. Results are on training-period data only; the holdout was
not read. Window A: fit to 9 Jun 2026, validate 10 Jun to 5 Aug (46,656 rows). Window B: fit to
31 Dec, validate 1 Jan to 30 Apr (about 102,000 rows). Error is WAPE against units sold.

| Variant | Window A | Window B |
|---|---|---|
| full model | 19.3% | 20.3% |
| without weather | 19.8% (+0.49) | 20.2% (-0.12) |
| without festival, payday, school holiday | 19.4% (+0.09) | 20.5% (+0.24) |
| without weekday and weekend | 20.7% (+1.34) | 22.3% (+2.03) |
| without prices and promotions | 19.8% (+0.48) | 20.4% (+0.08) |
| without recent stock-outs | 19.3% (-0.02) | 20.2% (-0.06) |
| weather with forecast-like error | 19.4% (+0.10) | 20.3% (+0.05) |
| refit every week | 19.2% (-0.12) | 19.8% (-0.45) |
| managers' rule | 22.4% | 23.0% |

## What it says
- **Weekday and weekend matter most** (+1.3 and +2.0 points when removed; in window B the
  forecast also runs 7% low without it).
- **Weather helps only in window A** (+0.5 points; on heavy-rain days +2.2 points, in both
  windows 22% against 20%). Over the whole of window B it does nothing overall. Its value is
  concentrated on heavy-rain days, as the data findings said.
- **Festival and payday add little overall** (0.1 to 0.2 points); their value is on a few days.
- **Prices and promotions** matter in window A, not in window B.
- **Recent stock-out flags** add nothing once demand is already rebuilt for sold-out days.
- **Noisy weather costs almost nothing** (+0.1 and +0.05 points). The noise level
  (2 degrees, 5 mm rain) is an assumption, not a measured forecast error.
- **Refitting weekly beats fitting once** (-0.1 and -0.45 points), the case for the weekly retrain.
- Every variant beats the managers' rule (22.4% and 23.0%).

## Waste and stock-outs (window A only; same supply split, spot buying trimmed)
Managers' split simulated: waste 7.8%, stock-outs 10.5%. Full model: 5.6% and 7.0%. Walk-in
stores 5.5% and 7.3%; dark stores 5.9% and 6.5%. Dropping weather lowers waste (5.1%) but raises
stock-outs (8.4%): it trades one for the other, so it does not count as an improvement. Farmer
share is unchanged by construction here (committed farmer volume is never reduced) but was not
re-measured in this run.

## Limits
- Replay was run for window A only. Two windows, one data pack: differences under about 0.2
  points are noise.
- The forecast-like weather noise is assumed. Weather is the observed value, not a forecast.
