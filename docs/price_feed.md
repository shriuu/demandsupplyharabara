# Live mandi price feed

Status on 3 November 2026: **built and tested against fixtures; not yet confirmed against a real
data.gov.in answer** (no API key was available to the build session). Real prices are for the
DC lead's display only. The demand model keeps training on the pack's synthetic prices (ADR-0005).

## What was checked (read-only, a handful of requests, descriptive User-Agent)

| Route | Result |
|---|---|
| data.gov.in `api.data.gov.in/resource/...` | Answers `Authorization field missing` without a key. So a free key is required and is the user's to create. Resource id in `config/feeds.yaml` is **unverified** (from memory, not confirmed). |
| CEDA `agmarknet.ceda.ashoka.edu.in/api/categories` | Works. |
| CEDA `/api/states?commodity_id=1` | Works (Karnataka = id 29). `/api/states` with no parameter: HTTP 500. |
| CEDA `/api/districts?state_id=29` | Works. Bangalore = id 572, Bangalore Rural = 583. |
| CEDA `/api/commodities?state_id=29` | Works (453 commodities). Without a parameter: HTTP 500. |
| CEDA `POST /api/prices` (state 29, district 572, Tomato id 78, daily) | One window (1 Oct to 3 Nov 2026) returned `{"data":[]}`: **no daily Bangalore tomato rows**. Four other windows (2024 to 2026, daily and monthly) returned HTTP 500 "Error accessing the prices from the database". |

Findings:
- **Product coverage in CEDA's commodity list is complete by name**: all 25 products match
  (Tender Coconut = id 200, Capsicum = 164, Chilli Capsicum = 88, Bhindi (Ladies Finger) = 85,
  Beans = 94, and so on).
- **Whether Bengaluru markets have usable daily rows is NOT confirmed.** The prices endpoint
  was failing or empty on every try, and its response shape was never seen, so no CEDA parser
  was written (that would be guessing). The route is not usable today.
- I did not confirm which Bengaluru markets (Yeshwanthpur, Binny Mill, K.R. Market) report.
- Terms: CEDA's site says the data is DMI, Ministry of Agriculture and Farmers Welfare; I could
  not find a licence text. data.gov.in data is published under the Government Open Data
  License - India (GODL); the user should confirm this on the resource page. Both are cited.

## What is built

`harabhara/data/external.py`: `MandiPriceClient.quote(sku_id, product)` returns a `PriceQuote`.
- Rupees per quintal from the feed are shown as rupees per kg (`kg_per_quintal` in config).
- Always carries the citation in `source`. No key, feed down, empty or unreadable answer, or an
  unmapped product gives `status="unavailable"` with no price.
- Cache on disk (one file per commodity). A fresh cache is reused (`cache_ttl_hours`); when the
  feed fails, an older cache is shown as `stale` after `stale_after_hours`, and not at all after
  `drop_after_hours`. A price dated older than `price_max_age_days` is also `stale`.
- One request per commodity per cache period, `User-Agent` from config, rows kept in the cache
  for a short history (`history_keep_days`).
- `Tender Coconut` is never quoted: Agmarknet's unit for it (possibly per 100 nuts) is unverified.
  `Capsicum` maps to the feed's "Capsicum"; "Chilli Capsicum" (a separate commodity) is not used.

`harabhara/data/prices.py`: `price_shock(history, today, lookback_days, ratio_threshold)` gives
`up`, `down`, `none` or `unknown` (never guessed). **data.gov.in's daily resource holds only the
latest days**, so the shock check works from the history the cache builds up. It reads
`unknown` until the cache holds a price from a week earlier. The nightly job must therefore call
`quote` for every product every day, or the shock flag stays `unknown`.

All limits are in `config/feeds.yaml`; values marked ASSUMED are engineering defaults.

## What the user must do
1. Create a free key on data.gov.in (sign up, then "My Account" > API key).
2. Locally: put `DATA_GOV_IN_API_KEY=...` in the git-ignored `.env`. In the cloud: store it in
   Secret Manager and expose it to Cloud Run as that environment variable.
3. With the key set, run one quote for Tomato and compare the field names and the resource id
   with `parse_records` and `config/feeds.yaml`; fix both if they differ.
