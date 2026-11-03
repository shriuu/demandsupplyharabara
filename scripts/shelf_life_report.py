"""Evaluate the shelf-life model against the fixed rule on unseen QC samples.

Fits on samples up to `fit_until` and scores the rest of the TRAINING period. QC samples dated in
the holdout are never read here. Prints aggregates only. Usage:
    uv run python scripts/shelf_life_report.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from harabhara.models.shelf_life import FEATURES, TARGET, ShelfLifeModel, rule_cap, rule_days
from harabhara.settings import load_config

PACK = Path(__file__).resolve().parents[1] / "work" / "PS-10_procurement_and_inventory.xlsx"


def mae(a: pd.Series, b: pd.Series) -> float:
    return float((a - b).abs().mean())


def main() -> None:
    cfg = load_config()
    p = cfg.modeling.shelf_life
    qc = pd.read_excel(PACK, sheet_name="qc_samples")
    rules = pd.read_excel(PACK, sheet_name="shelf_life_rules")
    cats = rules[["sku_id", "category"]]
    qc["date"] = pd.to_datetime(qc["date"])
    qc = qc[qc["date"] <= pd.Timestamp(p.training_period_end)].merge(cats, on="sku_id")
    fit = qc[qc["date"] <= pd.Timestamp(p.fit_until)]
    valid = qc[qc["date"] > pd.Timestamp(p.fit_until)].copy()
    print(f"fit samples: {len(fit):,}; validation samples (unseen dates): {len(valid):,}\n")

    model = ShelfLifeModel(p).fit(fit)
    cap = rule_cap(valid, rules, cfg.rules.receiving)
    est = model.predict(valid, cap)
    free = model.predict(valid, pd.Series(1e9, index=valid.index))  # without the rule cap
    truth = valid[TARGET]
    plain_rule = rule_days(valid, rules)

    print("| Estimator | MAE (days) | Bias (days) |")
    print("|---|---|---|")
    for name, pred in (
        ("Fixed rule", plain_rule),
        ("Rule with warm-arrival penalty", cap),
        ("Model, likely, no rule cap (for comparison)", free.likely),
        ("Model, likely, capped by the rule", est.likely),
        ("Model, whole days (rounded down)", est.likely_days().astype(float)),
    ):
        print(f"| {name} | {mae(pred, truth):.2f} | {float((pred - truth).mean()):+.2f} |")

    print("\n| Category | n | Rule MAE | Model MAE |")
    print("|---|---|---|---|")
    for cat, g in valid.groupby("category"):
        i = g.index
        print(
            f"| {cat} | {len(g)} | {mae(cap[i], truth[i]):.2f} | {mae(est.likely[i], truth[i]):.2f} |"
        )

    warm = valid["receipt_temperature_c"] > cfg.rules.receiving.hot_arrival_temp_c
    print("\n| Arrival | n | Rule MAE | Model MAE |")
    print("|---|---|---|---|")
    for label, mask in (("Warm (above limit)", warm), ("Not warm", ~warm)):
        i = valid.index[mask]
        print(
            f"| {label} | {len(i)} | {mae(cap[i], truth[i]):.2f} | {mae(est.likely[i], truth[i]):.2f} |"
        )

    inside = ((truth >= est.low.apply(lambda v: v - 0.5)) & (truth <= est.high + 0.5)).mean()
    print(
        f"\n- Observed life inside the low-to-high range (with half a day of rounding): {inside:.1%}"
    )
    free_inside = ((truth >= free.low - 0.5) & (truth <= free.high + 0.5)).mean()
    print(f"- Same range without the cap: {free_inside:.1%}")
    print(f"- Model said more than the rule allows (so the cap applied): {est.capped.mean():.1%}")
    print(f"- Observed life above the capped rule: {(truth > cap).mean():.1%}")

    # Brief test T09: tomato, 2 days since harvest, 31C, firmness 5.8
    typical = fit[fit["sku_id"] == "P01"]
    case = pd.DataFrame(
        [
            {
                "sku_id": "P01",
                "source_type": "Mandi auction",
                "grade_assigned": "B",
                "days_since_harvest": 2,
                "receipt_temperature_c": 31.0,
                "firmness_score_1_10": 5.8,
                "colour_score_1_10": float(typical["colour_score_1_10"].median()),
                "visible_defects_pct": float(typical["visible_defects_pct"].median()),
            }
        ]
    )[FEATURES]
    t9_cap = rule_cap(case, rules, cfg.rules.receiving)
    t9 = model.predict(case, t9_cap)
    fixed = rule_days(case, rules).iloc[0]
    print(
        f"\nT09 (tomato, 2 days since harvest, 31 C, firmness 5.8, grade B): fixed rule {fixed:.0f} days, "
        f"rule with warm penalty {t9_cap.iloc[0]:.0f}, model likely {t9.likely.iloc[0]:.1f} "
        f"(range {t9.low.iloc[0]:.1f} to {t9.high.iloc[0]:.1f})"
    )


if __name__ == "__main__":
    main()
