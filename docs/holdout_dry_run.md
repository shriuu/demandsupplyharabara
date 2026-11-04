# Dry run results (2026-06-11 to 2026-08-05)

## T01: forecast error against units sold, same rows
| Forecast | WAPE | Bias | Rows |
|---|---|---|---|
| Model | 19.2% | -1.5% | 15,264 |
| Managers' rule | 22.5% | -0.0% | 15,264 |

Share of outcomes inside the stated range: 82.4%

### By category
| category | n | Model WAPE | Model bias | Managers WAPE | Managers bias |
|---|---|---|---|---|---|
| Fruits | 4512 | 0.207 | -0.017 | 0.240 | -0.002 |
| Leafy greens | 2688 | 0.176 | -0.026 | 0.210 | -0.003 |
| Vegetables | 8064 | 0.194 | -0.008 | 0.227 | 0.002 |

### By weekday
| t_dow | n | Model WAPE | Model bias | Managers WAPE | Managers bias |
|---|---|---|---|---|---|
| 0.000 | 2184 | 0.201 | -0.031 | 0.235 | 0.102 |
| 1.000 | 2184 | 0.204 | -0.027 | 0.240 | 0.114 |
| 2.000 | 2160 | 0.205 | -0.030 | 0.230 | 0.092 |
| 3.000 | 2184 | 0.194 | -0.007 | 0.221 | 0.068 |
| 4.000 | 2184 | 0.182 | -0.008 | 0.195 | -0.006 |
| 5.000 | 2184 | 0.188 | 0.010 | 0.218 | -0.120 |
| 6.000 | 2184 | 0.175 | -0.016 | 0.235 | -0.167 |

### By heavy rain
| t_heavy_rain | n | Model WAPE | Model bias | Managers WAPE | Managers bias |
|---|---|---|---|---|---|
| 0.000 | 12792 | 0.190 | -0.016 | 0.221 | -0.010 |
| 1.000 | 2472 | 0.199 | -0.005 | 0.246 | 0.053 |

## T10: replay, waste / empty shelves / margin together
| Scenario | Waste | Empty shelves | Gross margin |
|---|---|---|---|
| Managers' split (simulated) | 7.74% | 10.62% | 36.14% |
| Our split, spot trimmed | 5.79% | 6.51% | 37.08% |

Farmer groups: committed volume unchanged; sku-days delivered below it: 0 (must be 0).
Farmer-group share of supply: 31.1% actual, 31.5% with spot trimming.

By store type and category (change against the managers' split, in points: waste / empty shelves):

category:
- Fruits: -1.30 / -5.76
- Leafy greens: -4.58 / -1.90
- Vegetables: -0.53 / -3.92

store type:
- Dark store: -0.53 / -6.80
- Store: -2.60 / -2.76

Limits: one data pack; demand does not respond to extra stock or to markdowns in the replay.
