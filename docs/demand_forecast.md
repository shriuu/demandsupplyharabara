# Demand forecast

Code: `harabhara/features/build.py`, `harabhara/models/demand.py`, `calibrate.py`, `cold_start.py`.
Settings: `config/modeling.yaml` (`demand`). Report: `scripts/demand_report.py` (aggregates only).

## What it does
One CatBoost model for every store and product forecasts demand one, two and three days ahead
as a low, likely and high value (10th, 50th, 90th percentile). A forecast made on the evening of
day *o* uses only data up to *o*: recent demand (sold-out days corrected, the S07 till outage
rebuilt), the same weekday in earlier weeks, the target day's calendar (weekday, payday, school
holiday, festival intensity, and the intensity of the *next* day's festival so eves are visible),
the target day's weather, and shelf and mandi price at the origin. Festivals enter as
intensity, not names, so a festival never seen in training is treated like similar ones.

Two rules sit around the model:
- **Cold start.** A product with fewer than seven observed days in the last 28, or one the model
  never trained on, is not forecast by the model. The recent average takes over with a
  fixed-width range and a `thin_history` flag. With no history at all there is no forecast.
- **Calibrated range.** The low-to-high range is widened or tightened on a calibration window so
  it holds about 80% of outcomes.

`tests/model/test_features_point_in_time.py` changes every sales, price and stock-out figure after
the forecast day and checks that no feature moves.

## Results (the calendar's holdout has NOT been read)
Two validation windows, each fit only on data before it:

| Window | Fit on | Model WAPE | Managers' rule WAPE | Model bias |
|---|---|---|---|---|
| 10 Jun to 5 Aug 2026 (eight weeks, same length as the holdout) | Oct 2025 to 9 Jun 2026 | **19.3%** | 22.4% | -0.6% |
| 1 Jan to 30 Apr 2026 (festivals, heat, seasonal fruit) | Oct to Dec 2025 only | **20.3%** | 23.0% | -0.5% |

Measured against units sold, as the brief does. The brief's target is 19% WAPE and bias within
3%. The first window is at the line and the second is above it, so **the target is not shown to be
met**; it will be known only after the single holdout run.

Same accuracy at one, two and three days ahead (19.2 / 19.3 / 19.5% in the first window).

### Where the model wins
- Weekends: 18.2% vs 22.6% (first window); the managers' rule is 14% under-forecast at weekends
  and 7% over on weekdays.
- Heavy-rain days: 20.1% vs 24.5%.
- **Festival eves** (second window): festival-sensitive products (banana, coconut, pomegranate)
  19.9% vs 23.4%, with bias -5.5% vs -14.3% for the managers' flat bump. Onions on the same days
  20.8% vs 24.1%, bias -1.2%: they stay near normal instead of getting a blanket increase.
- 22 of 25 products beat the managers' rule; the other three (mango, grapes, watermelon in the
  second window) use the fallback and match it. No product is worse.

### Where it is weak or unproven
- **New seasons.** In the second window the three seasonal fruits were absent from the fitting
  data, so the model treats them as new products. Without the fallback it was off by 86%; with it,
  38%, equal to the managers' rule. The fallback does not beat the managers' rule, it only stops
  the model doing worse. With one season of data, a *second season of a known product* cannot be
  tested at all. The August-September holdout has no seasonal products in season.
- **Tomato.** In the summer window the model over-forecasts tomato by 13.5% (error 23.9% vs 23.4%
  for the rule). The cause was not established. Prices swung in that window, but that is an
  untested guess.
- **Range honesty.** After calibration the range holds 79.2% of outcomes in the first window and
  77.8% in the second, a little under the 80% target. Leafy greens are lowest (74.9% in the second
  window). Calibration by horizon and category is still to do.
- **Sold-out days.** The model forecasts demand, so on days that sold out its forecast is
  15% above units sold. That is intended, not an error.
- **Weather is the observed value**, standing in for a forecast. A real forecast is noisier, so
  these numbers are somewhat optimistic. The noise robustness run is still to do, as are runs with
  weather removed and prices blank.
- **Settings were not tuned.** The first values tried are the ones in use. Rolling-origin tuning
  and the LightGBM challenger are still to do.
- Heat and festival slices are small in places (72 rows per product on major eves), so
  per-product numbers there are indicative only.
