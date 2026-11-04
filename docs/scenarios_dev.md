# Acceptance scenarios checked on training data (4 Nov 2026)

Method: fit on data before 5 Aug, take the 28 days before, change one input, compare forecasts.
The holdout was not read. T03 on its real festival can only be scored at the holdout run.

| Scenario | Result | Verdict |
|---|---|---|
| **T04** heavy rain | Walk-in stores 0.88x, dark stores 1.04x (data: 0.89x and 1.05x). `tests/scenarios/test_t04_heavy_rain.py` | Pass |
| **T06** sold out at 2 pm | Estimate is above units sold and capped; `tests/model/test_hidden_demand.py` | Pass |
| **T03** festival eve (proxy: full festival intensity on training rows) | Bananas 1.64x, coconut 1.75x, onion 1.26x | **Partly.** Direction right, but onion should be almost unchanged. History shows onion between 0.76x and 1.33x on festival eves, so the data itself is noisy. Scored properly at the holdout run. |
| **T05** tomato mandi price doubles | Tomato forecast changes by -1.5% (shelf price doubled: -1.6%) | **Weak.** The brief expects clearly lower demand. The data's largest 7-day rise is 1.4x, so the model never saw a doubling, and trees do not extrapolate. The price warning to the buying lead needs a mandi feed, which is not connected. |

## Gaps found while checking the playbook
- **Transfer distance (PB11):** the 6 km limit cannot be enforced. The pack has no coordinates for
  stores (owner question 15), and every pair of stores appears in the transfer log, so the reach
  rule allows all of them. Transfers are checked for the van cost, the arrival time and the
  approver, not the distance.
- **Cold-room and crate-stack rules (PB04, PB05):** these are receiving-dock rules. The tool gives
  no storage or stacking instruction, so there is nothing for it to enforce. Listed for the handover.
- **Payment terms (PB18):** the tool never pays farmer groups; it only checks that no price
  recommendation goes below the contract floor (guardrail 2).
- **Shelf life counted from arrival (PB06):** lot ages are inferred from deliveries because the
  pack has no lot data (owner question 6).
