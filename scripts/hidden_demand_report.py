"""Run the hidden-demand estimator on the data pack and print a Markdown summary.

Aggregates only: no row-level data is printed. Uses the training split for the stress test so
the holdout stays untouched. Usage: uv run python scripts/hidden_demand_report.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from harabhara.data.clean import clean_sales, load_sales, load_sheet
from harabhara.features.hidden_demand import (
    estimate_demand,
    hours_by_format,
    validate_by_truncation,
)
from harabhara.settings import load_config

SALES = Path(__file__).resolve().parents[1] / "work" / "PS-10_store_sales_daily.xlsx"
GAMMAS = (0.6, 0.8, 1.0, 1.25, 1.5)


def main() -> None:
    cfg = load_config()
    params = cfg.modeling.hidden_demand
    hours = hours_by_format(cfg.schedule.store_hours)
    stores = load_sheet(SALES, "stores")[["store_id", "format"]]
    skus = load_sheet(SALES, "skus")[["sku_id", "sku_name", "category"]]
    df = clean_sales(load_sales(SALES)).data.merge(stores, on="store_id").merge(skus, on="sku_id")
    usable = df[df["usable_for_targets"]]
    est = estimate_demand(usable, hours, params)

    flagged = est[est["demand_estimated"]]
    uplift = flagged["demand"] / flagged["sold_corrected"]
    print(f"- In-season usable rows: {len(est):,}; sold-out rows corrected: {len(flagged):,}")
    print(
        f"- Share of units that were hidden: {(est['demand'].sum() / est['sold_corrected'].sum() - 1):.2%}"
    )
    print(
        f"- Uplift on corrected rows: median {uplift.median():.2f}x, 90th pct {uplift.quantile(0.9):.2f}x, max {uplift.max():.2f}x"
    )
    print(
        f"- Rows at the lower bound of day-share: {(flagged['sold_out_hour'].sub(flagged['format'].map(lambda f: hours[f].open)).div(flagged['format'].map(lambda f: hours[f].close - hours[f].open)) < params.min_fraction_of_day).sum()}"
    )

    print("\n| Category | Sold-out rows | Hidden units, % of sold |")
    print("|---|---|---|")
    for cat, g in est.groupby("category"):
        hidden = g["demand"].sum() / g["sold_corrected"].sum() - 1
        print(f"| {cat} | {int(g['demand_estimated'].sum()):,} | {hidden:.2%} |")

    weekend = est["date"].dt.dayofweek >= 5
    for label, mask in (("Weekend", weekend), ("Weekday", ~weekend)):
        g = est[mask]
        print(f"\n- {label}: hidden units {g['demand'].sum() / g['sold_corrected'].sum() - 1:.2%}")

    train = est[(est["split"] == "train")]
    honest = train[~train["demand_estimated"]]
    shares = (
        flagged.loc[flagged["split"] == "train"]
        .assign(
            share=lambda x: (
                (x["sold_out_hour"] - x["format"].map(lambda f: hours[f].open))
                / x["format"].map(lambda f: hours[f].close - hours[f].open)
            )
        )["share"]
        .clip(lower=params.min_fraction_of_day, upper=1.0)
        .to_numpy()
    )
    print(
        "\nStress test on days that did not sell out (training split only). The estimator assumes"
    )
    print(
        f"an even pace (gamma {params.intraday_profile_gamma}); each row changes the true pace.\n"
    )
    print("| True pace (gamma) | Bias | WAPE |")
    print("|---|---|---|")
    for gamma in GAMMAS:
        r = validate_by_truncation(honest, hours, params, np.asarray(shares), gamma, seed=0)
        print(f"| {gamma} | {r.bias:+.2%} | {r.wape:.2%} |")


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
