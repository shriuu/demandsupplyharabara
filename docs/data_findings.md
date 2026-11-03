# Data pack findings (first pass, 2 Nov 2026)

Source copies: `source_readonly/` (write-protected). Working copies: `work/`. Analysis code in `scripts/` and inline runs. These figures still need to be turned into pipeline code with tests in `data/validate.py`.

## 1. The brief's numbers reproduce exactly

| Measure | Brief | Ours |
|---|---|---|
| Wastage (in-season, units) | 8.2% | 8.19% |
| Stock-out rate | 9.1% | 9.11% (weekend 14.2%, weekday 7.1%) |
| Waste by category | greens 15.5, fruit 6.6, veg 4.7 | 15.55 / 6.64 / 4.72 |
| Walk-in vs dark store waste | 8.7 vs 7.1 | 8.67 vs 7.13 |
| Waste at cost | ₹86 lakh | ₹85.3 lakh (cost = qty-weighted purchase price per product) |
| Revenue, gross margin | ₹20.0 cr, 34.7% | ₹20.02 cr, 34.7% |
| 7-day avg rule, holdout WAPE | 23.6% | 23.58% (bias −0.1%) |
| Same day last week WAPE | 28.7% | 28.74% |

Managers' actual orders vs next-day sales on the holdout: **+10.1% bias, 35.8% WAPE**. Their orders are worse than their own rule, because of the buffer.

So our definitions match the problem owner's. The metric code can be checked against these numbers.

## 2. Data quality: all known issues confirmed and fixable

- **25 exact duplicates.** These are also duplicate keys (date, store, sku), so drop them.
- **120 blank `wastage_units`.** These can be rebuilt exactly from `opening + received − sold − closing` (range 0–64).
- **S07 POS outage, 10–12 Feb 2026.** These 69 rows are the *only* ones where stock arithmetic doesn't balance. The gap equals the unrecorded sales, so **true sales can be rebuilt from arithmetic** instead of throwing the rows away. We still exclude them from training targets to be safe, and use the rebuilt values only for lag features.
- Opening stock equals the previous day's closing on 99.7% of rows, and received units equal the previous night's order on 99.7%. The ledger can rely on both.
- `stockout_flag` ⇔ `sold_out_hour` present: they match one-to-one. In 6,990 rows closing stock is 0 without a stock-out (stock was binned at close). This is not censored.
- Out-of-season rows: 9,144. These are excluded from all metrics.

## 3. Censoring (sold-out days)

- 9,146 sold-out rows. The median sold-out hour is **20:27**, and 25% sell out before 18:54. Most censoring is late in the day and mild, so a sold-out-hour-based fix (scale by the expected intraday share remaining) is well-founded.
- Festival eves for bananas, coconut and pomegranate sell out 13.5% of the time. The uplift we see in sales (median 1.2–1.9×) **understates** the "several-fold" demand the brief describes.

## 4. Festivals: the two acceptance-test festivals never appear in training

- Train covers Dasara, Deepavali, Sankranti, Shivaratri, Ugadi, Eid, Ram Navami and others.
- **Varamahalakshmi (21 Aug) and Ganesha Chaturthi (14 Sep) fall only in the holdout.** T3 can't be learned from examples of that festival. Per-product uplift has to come from *intensity × product sensitivity*, pooled across the major festivals (intensity ≥ 0.9). CLAUDE.md's "pull toward similar festivals" is required, not optional.
- Sales-based uplift on major-festival eves (train): bananas 1.2–1.9×, coconut 1.2–1.9×, pomegranate 1.3–1.65×, **onion 0.76–1.33×** (sometimes below normal). The flat 25% rule is clearly wrong in both directions.

## 5. Weather and price

- Heavy rain (≥15 mm), median ratio to normal: **walk-in 0.89×, dark store 1.05×**. This direction matches T4.
- Hot days (top 10% max temp): watermelon 1.18×, coconut 1.12×.
- Tomato: within-store price elasticity ≈ **−0.85** (shelf ₹26–₹118). Mandi ₹16.1–₹64.1. **The largest 7-day rise in the data is 1.4×, so prices never double in a week.** T5 is a scenario we will have to inject into a test, because no historical day shows it.

## 6. Shelf life (QC)

- The fixed rule has MAE **0.85 days** with bias +0.4 (it overstates life). Adding the playbook's >30 °C −1 day penalty gives MAE 0.81.
- Error by age at receipt: day 0 +0.55 d (rule too short), day 3 **−1.31 d** (rule too long). Age is the main signal the rule ignores, which fits T9.
- Observed life is longer than the rule on 20% of samples. This conflicts with "rule caps the model" (owner Q14).
- Grades disagree with the firmness bands on 12% of samples (the README warns grades are human-assigned).
- Mandi produce is 1–3 days old and 7.5% grade C. FPO produce is 0–1 days old and has no grade C.

## 7. Farmers

- **No FPO purchase was ever paid below its contract floor** (5,311 lines). On 49 days the mandi price dropped below the floor, and the floor held.
- FPO share of volume is 0.35–0.38 for every FPO product. That is above target for FPO-01 and 03–06 but **below target for FPO-02 greens (0.54), FPO-07 coconut (0.49) and FPO-08 Ooty veg (0.49)**.
- DC purchases are about 1.025× store receipts.

## 8. Transfers

- 1,147 logged transfers across 132 store pairs, all "stock-out at receiving store". The median is 12 units, and **75% are under 20 units**, the size the playbook says rarely pays.
- **No store coordinates**, so the 6 km rule can't be enforced from the data (owner Q15).

## 9. Waste and stock-outs by product (in-season, full year)

Highest waste: coriander 18.0%, methi 17.9%, palak 17.8%, bhindi 14.4%, beans 13.9%, bananas 10–11%, papaya 9.9%.
Highest stock-outs: mango 25.3%, watermelon 23.4%, grapes 20.1%, pomegranate 15.5%, apple 14.3%. The seasonal fruit sells out most, which shows cold-start under-ordering.
Waste and stock-outs fall on **different products**. That is where the profit is: cut the greens buffer, and raise the order for seasonal fruit at the start of its season.
