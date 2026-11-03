"""Train the demand forecast on the early training period and score it on the later one.

Inner validation only: the calendar's holdout is never read. Prints aggregates. Usage:
    uv run python scripts/demand_report.py
"""

from __future__ import annotations

import argparse
import time
from datetime import date
from pathlib import Path

import pandas as pd

from harabhara.data.prepare import build_examples, build_panel
from harabhara.features.build import feature_columns
from harabhara.models.calibrate import apply_shift, conformal_shift, coverage
from harabhara.models.cold_start import apply_thin_history
from harabhara.models.demand import DemandModel
from harabhara.settings import load_config
from harabhara.sim.evaluation import by_slice, score

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "work" / "PS-10_store_sales_daily.xlsx"
EXTERNAL = ROOT / "work" / "PS-10_external_factors.xlsx"
CALIBRATION_DAYS = 28
SEASONAL = ["P07", "P10", "P11"]  # mango, grapes, watermelon


def pct(x: float) -> str:
    return f"{x:+.1%}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-until", type=date.fromisoformat)
    parser.add_argument("--validate-from", type=date.fromisoformat)
    parser.add_argument("--validate-to", type=date.fromisoformat)
    args = parser.parse_args()
    cfg = load_config()
    p = cfg.modeling.demand.model_copy(
        update={
            k: v
            for k, v in {
                "fit_until": args.fit_until,
                "validate_from": args.validate_from,
                "validate_to": args.validate_to,
            }.items()
            if v is not None
        }
    )
    started = time.time()
    panel, report = build_panel(SALES, EXTERNAL, cfg)
    examples = build_examples(panel, cfg)
    print(
        f"data: {report.rows_in:,} rows in, {report.duplicates_removed} duplicates, "
        f"{report.blank_waste_rebuilt} blank waste rebuilt, {report.outage_store_days} outage store-days"
    )
    print(f"examples: {len(examples):,} (built in {time.time() - started:.0f}s)\n")

    usable = (
        (examples["t_usable"] == 1) & (examples["t_in_season"] == 1) & examples["y_demand"].notna()
    )
    train_mask = (
        usable
        & (examples["t_split"] == "train")
        & (examples["target_date"] <= pd.Timestamp(p.fit_until))
    )
    valid_mask = (
        usable
        & (examples["target_date"] >= pd.Timestamp(p.validate_from))
        & (examples["target_date"] <= pd.Timestamp(p.validate_to))
    )
    assert not (examples.loc[valid_mask, "t_split"] == "holdout").any()
    train, valid = examples[train_mask].copy(), examples[valid_mask].copy()
    columns = feature_columns(examples)
    print(
        f"fit rows: {len(train):,} (targets up to {p.fit_until}); validation rows: {len(valid):,} "
        f"({p.validate_from} to {p.validate_to}); features: {len(columns)}"
    )

    started = time.time()
    model = DemandModel(p).fit(train, columns)
    print(f"trained in {time.time() - started:.0f}s")
    model_only = model.predict(valid)
    forecast = apply_thin_history(
        model_only,
        valid,
        p.min_history_days,
        p.thin_history_range_width,
        model.unseen(valid),
    )
    valid["f_low"], valid["f_likely"], valid["f_high"] = (
        forecast["low"],
        forecast["likely"],
        forecast["high"],
    )
    valid["f_model_only"] = model_only["likely"]
    valid["thin"] = forecast["thin_history"]
    valid["f_managers"] = valid["sold_mean_7"]
    valid = valid.dropna(subset=["f_managers", "f_likely"])
    print(f"thin-history rows handled by the fallback: {int(valid['thin'].sum()):,}")

    models = {
        "Model": "f_likely",
        "Model, no cold-start rule": "f_model_only",
        "Managers' rule": "f_managers",
    }
    print("\n## Overall, against units sold (the brief's measure)")
    for name, col in models.items():
        s = score(valid, col, "y_sold")
        print(f"- {name}: WAPE {s['wape']:.1%}, bias {pct(s['bias'])}  (n={int(s['n']):,})")
    honest = valid[valid["t_demand_estimated"] == 0]
    print("\n## Against true demand on days that did not sell out")
    for name, col in models.items():
        s = score(honest, col, "y_demand")
        print(f"- {name}: WAPE {s['wape']:.1%}, bias {pct(s['bias'])}  (n={int(s['n']):,})")

    def show(title: str, frame: pd.DataFrame, column: str) -> None:
        print(f"\n## {title}")
        table = by_slice(frame, column, models, "y_sold")
        print(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    show("By horizon", valid, "horizon")
    show("By category", valid.assign(category=valid["category"]), "category")
    show("By store type", valid, "format")
    valid["weekend"] = valid["t_is_weekend"].map({1: "weekend", 0: "weekday"})
    show("Weekend vs weekday", valid, "weekend")
    valid["festival"] = pd.cut(
        valid["t_eve_intensity"], [-1, 0, 0.8, 2], labels=["none", "minor eve", "major eve"]
    )
    show("Day before a festival", valid, "festival")
    valid["rain"] = valid["t_heavy_rain"].map({1: "heavy rain", 0: "no heavy rain"})
    show("Heavy rain", valid, "rain")
    hot = panel.loc[panel["split"] == "train", "max_temp_c"].quantile(0.9)
    valid["heat"] = (valid["t_max_temp_c"] >= hot).map({True: "hot day", False: "normal"})
    show(f"Hot days (max temperature at or above {hot:.1f} C, top 10% of the year)", valid, "heat")
    valid["soldout"] = valid["t_stockout"].map({1: "sold out", 0: "did not sell out"})
    show("Sold-out days (units sold understate demand)", valid, "soldout")
    major = valid[valid["t_eve_intensity"] >= 0.8]
    if len(major):
        kind = major["festival_sensitive"].map({1: "festival-sensitive", 0: "other"})
        show("Major festival eves, by product type", major.assign(kind=kind), "kind")
        show(
            "Major festival eves, festival-sensitive products",
            major[major["festival_sensitive"] == 1],
            "sku_id",
        )
        show(
            "Major festival eves, onions (should stay near normal)",
            major[major["sku_id"] == "P02"],
            "sku_id",
        )
    seasonal = valid["days_in_season"].le(14) & valid["sku_id"].isin(SEASONAL)
    valid["season"] = seasonal.map({True: "first two weeks of a season", False: "established"})
    show("New-season days", valid, "season")

    product = by_slice(valid, "sku_id", models, "y_sold")
    product["gain"] = product["Managers' rule WAPE"] - product["Model WAPE"]
    print("\n## Products where the model is worse than the managers' rule")
    worse = product[product["gain"] < 0]
    print(worse.to_string(index=False, float_format=lambda v: f"{v:.3f}") if len(worse) else "none")
    print(f"\nproducts where the model is better: {(product['gain'] > 0).sum()} of {len(product)}")

    print("\n## Range honesty (low-to-high should hold about 80% of outcomes)")
    first_cal = pd.Timestamp(p.validate_from) + pd.Timedelta(days=CALIBRATION_DAYS)
    steady = valid[~valid["thin"]]
    cal = steady[steady["target_date"] < first_cal]
    test = steady[steady["target_date"] >= first_cal]
    raw = test[["f_low", "f_likely", "f_high"]].rename(columns=lambda c: c.removeprefix("f_"))
    shift = conformal_shift(
        cal["f_low"], cal["f_high"], cal["y_demand"], coverage=p.quantiles[2] - p.quantiles[0]
    )
    adjusted = apply_shift(raw, shift)
    print(
        f"- calibration window: {len(cal):,} rows; test window: {len(test):,} rows; shift {shift:+.2f} units"
    )
    print(
        f"- raw coverage {coverage(raw, test['y_demand']):.1%}; calibrated {coverage(adjusted, test['y_demand']):.1%}"
    )
    for category, group in test.groupby("category"):
        r = raw.loc[group.index]
        a = adjusted.loc[group.index]
        print(
            f"  - {category}: raw {coverage(r, group['y_demand']):.1%}, calibrated {coverage(a, group['y_demand']):.1%}"
        )

    print("\n## Most important features")
    print(model.importance().head(12).round(1).to_string())


if __name__ == "__main__":
    main()
