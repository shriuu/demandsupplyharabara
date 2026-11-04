# Holdout results (2026-08-06 to 2026-09-30)

## T01: forecast error against units sold, same rows
| Forecast | WAPE | Bias | Rows |
|---|---|---|---|
| Model | 19.5% | -0.6% | 14,784 |
| Managers' rule | 23.6% | -0.1% | 14,784 |

Share of outcomes inside the stated range: 82.2%

### By category
| category | n | Model WAPE | Model bias | Managers WAPE | Managers bias |
|---|---|---|---|---|---|
| Fruits | 4032 | 0.210 | -0.005 | 0.260 | -0.001 |
| Leafy greens | 2688 | 0.184 | -0.013 | 0.222 | 0.004 |
| Vegetables | 8064 | 0.196 | -0.003 | 0.235 | -0.004 |

### By weekday
| t_dow | n | Model WAPE | Model bias | Managers WAPE | Managers bias |
|---|---|---|---|---|---|
| 0.000 | 2112 | 0.202 | -0.008 | 0.256 | 0.098 |
| 1.000 | 2112 | 0.211 | 0.001 | 0.253 | 0.112 |
| 2.000 | 2112 | 0.202 | 0.001 | 0.247 | 0.127 |
| 3.000 | 2112 | 0.201 | -0.013 | 0.241 | 0.049 |
| 4.000 | 2112 | 0.187 | -0.022 | 0.215 | -0.054 |
| 5.000 | 2112 | 0.189 | 0.002 | 0.222 | -0.106 |
| 6.000 | 2112 | 0.180 | -0.004 | 0.226 | -0.153 |

### By heavy rain
| t_heavy_rain | n | Model WAPE | Model bias | Managers WAPE | Managers bias |
|---|---|---|---|---|---|
| 0.000 | 11352 | 0.193 | -0.009 | 0.230 | -0.018 |
| 1.000 | 3432 | 0.201 | 0.003 | 0.256 | 0.057 |

## T03: festival eves, forecast against actual (ratio to the product's own ordinary days)
| Product | Forecast uplift | Actual uplift |
|---|---|---|
| P01 | 1.05x | 0.98x |
| P02 | 1.05x | 1.03x |
| P03 | 1.04x | 0.98x |
| P04 | 1.16x | 1.29x |
| P05 | 1.23x | 1.25x |
| P06 | 1.09x | 1.15x |
| P08 | 1.09x | 1.12x |
| P09 | 1.16x | 1.13x |
| P12 | 1.21x | 1.29x |
| P13 | 1.10x | 1.20x |
| P14 | 1.07x | 1.06x |
| P15 | 1.06x | 1.06x |
| P16 | 1.08x | 1.13x |
| P17 | 1.06x | 1.08x |
| P18 | 1.07x | 1.06x |
| P19 | 1.07x | 1.05x |
| P20 | 1.08x | 1.07x |
| P21 | 1.07x | 1.09x |
| P22 | 1.06x | 0.99x |
| P23 | 1.09x | 1.05x |
| P24 | 1.09x | 1.03x |
| P25 | 1.08x | 1.20x |

## T10: replay, waste / empty shelves / margin together
| Scenario | Waste | Empty shelves | Gross margin |
|---|---|---|---|
| Managers' split (simulated) | 9.46% | 8.68% | 35.63% |
| Our split, spot trimmed | 5.76% | 6.00% | 37.47% |

Farmer groups: committed volume unchanged; sku-days delivered below it: 0 (must be 0).
Farmer-group share of supply: 31.8% actual, 32.9% with spot trimming.

By store type and category (change against the managers' split, in points: waste / empty shelves):

category:
- Fruits: -3.54 / -3.27
- Leafy greens: -6.70 / -0.26
- Vegetables: -1.80 / -3.19

store type:
- Dark store: -2.31 / -4.53
- Store: -4.37 / -1.76

Limits: one data pack; demand does not respond to extra stock or to markdowns in the replay.
