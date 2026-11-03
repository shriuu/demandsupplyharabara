"""Replay the later part of the training period with different splits of the same supply.

Forecasts come from a model fit only on data before the window, so nothing is seen early. The
calendar's holdout is never read. Usage:
    uv run python scripts/replay_report.py [--fit-until D --from D --to D --exponent X]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from harabhara.data.prepare import build_examples, build_panel
from harabhara.decisions.economics import unit_costs
from harabhara.features.build import feature_columns
from harabhara.models.cold_start import apply_thin_history
from harabhara.models.demand import DemandModel
from harabhara.settings import load_config
from harabhara.sim.metrics import gross_margin
from harabhara.sim.replay import ReplayParams, Scenario, replay

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "work" / "PS-10_store_sales_daily.xlsx"
EXTERNAL = ROOT / "work" / "PS-10_external_factors.xlsx"
PROC = ROOT / "work" / "PS-10_procurement_and_inventory.xlsx"
SCENARIOS: tuple[Scenario, ...] = ("managers", "reallocate", "reallocate_trim")
LABEL = {
    "managers": "Managers' split (simulated)",
    "reallocate": "Same supply, our split",
    "reallocate_trim": "Our split, spot buying trimmed",
}


def summarise(res: pd.DataFrame, category: pd.Series | None = None) -> dict[str, float]:
    live = res[res["in_season"]]
    delivered = float(live["delivered"].sum())
    return {
        "waste": float(live["binned"].sum() / delivered),
        "stockout": float((live["lost"] > 0).mean()),
        "lost_units": float(live["lost"].sum()),
        "margin": gross_margin(float(live["revenue"].sum()), float(live["cost"].sum())),
        "delivered": delivered,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-until", type=date.fromisoformat)
    parser.add_argument("--from", dest="start", type=date.fromisoformat)
    parser.add_argument("--to", dest="end", type=date.fromisoformat)
    parser.add_argument("--exponent", type=float)
    parser.add_argument("--floor", type=float)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--floors", type=lambda s: [float(x) for x in s.split(",")])
    args = parser.parse_args()
    cfg = load_config()
    dp = cfg.modeling.demand.model_copy(
        update={
            k: v
            for k, v in {
                "fit_until": args.fit_until,
                "validate_from": args.start,
                "validate_to": args.end,
            }.items()
            if v is not None
        }
    )
    exponent = (
        args.exponent if args.exponent is not None else cfg.modeling.decisions.waste_weight_exponent
    )

    panel, _ = build_panel(SALES, EXTERNAL, cfg)
    examples = build_examples(panel, cfg)
    usable = (
        (examples["t_usable"] == 1) & (examples["t_in_season"] == 1) & examples["y_demand"].notna()
    )
    train = examples[
        usable
        & (examples["t_split"] == "train")
        & (examples["target_date"] <= pd.Timestamp(dp.fit_until))
    ]
    day1 = examples[
        (examples["horizon"] == 1)
        & (examples["target_date"] >= pd.Timestamp(dp.validate_from))
        & (examples["target_date"] <= pd.Timestamp(dp.validate_to))
        & (examples["t_in_season"] == 1)
    ].copy()
    assert not (day1["t_split"] == "holdout").any(), "the holdout must not be read"
    cache = (
        ROOT
        / "artifacts"
        / f"replay_forecasts_{dp.fit_until}_{dp.validate_from}_{dp.validate_to}.pkl"
    )
    if cache.exists():
        forecasts = pd.read_pickle(cache)
    else:
        model = DemandModel(dp).fit(train, feature_columns(examples))
        raw = model.predict(day1)
        adjusted = apply_thin_history(
            raw, day1, dp.min_history_days, dp.thin_history_range_width, model.unseen(day1)
        )
        forecasts = adjusted[["low", "likely", "high"]].set_index(
            pd.MultiIndex.from_frame(day1[["store_id", "sku_id", "target_date"]])
        )

        cache.parent.mkdir(exist_ok=True)
        forecasts.to_pickle(cache)

    purchases = pd.read_excel(PROC, sheet_name="purchases")
    purchases["date"] = pd.to_datetime(purchases["date"])
    costs = unit_costs(purchases[purchases["date"] <= pd.Timestamp(dp.fit_until)])
    fpo = (
        purchases[purchases["source_type"] == "FPO contract"]
        .groupby(["date", "sku_id"])["quantity_units"]
        .sum()
    )
    total = purchases.groupby(["date", "sku_id"])["quantity_units"].sum()
    share = (fpo / total).fillna(0.0).reindex(total.index, fill_value=0.0)
    rules = pd.read_excel(PROC, sheet_name="shelf_life_rules").set_index("sku_id")
    life = {str(k): int(v) for k, v in rules["shelf_life_days_grade_A_ambient"].items()}
    params = ReplayParams(
        life_days=life,
        unit_cost={str(k): float(v) for k, v in costs.items()},
        markdown_pct=cfg.rules.markdown.step_1_pct,
        sales_order=cfg.modeling.projection.sales_order,
        quantiles=dp.quantiles,
        allocation_steps=cfg.modeling.decisions.allocation_steps,
        waste_exponent=exponent,
        basket_allowance=cfg.costs.basket_allowance_per_lost_sale_inr,
        service_floor=args.floor
        if args.floor is not None
        else cfg.modeling.decisions.service_level_floor,
    )

    window = panel[
        (panel["date"] >= pd.Timestamp(dp.validate_from))
        & (panel["date"] <= pd.Timestamp(dp.validate_to))
    ]
    live = window[window["usable_for_targets"]]
    print(
        f"window {dp.validate_from} to {dp.validate_to}; waste exponent {exponent}; "
        f"basket allowance {cfg.costs.basket_allowance_per_lost_sale_inr} (unset means 0)"
    )
    print(
        f"recorded history: waste {live['wastage_units'].sum() / live['received_units'].sum():.2%}, "
        f"stock-outs {live['stockout_flag'].mean():.2%}\n"
    )

    if args.sweep:

        def run(p: ReplayParams, s: Scenario) -> dict[str, float]:
            return summarise(
                replay(panel, forecasts, share, p, dp.validate_from, dp.validate_to, s)
            )

        base = run(params, "managers")
        print(
            "| Service floor | Waste | Stock-outs | Leafy-greens stock-outs | Lost units | Gross margin | Spot trimmed |"
        )
        print("|---|---|---|---|---|---|---|")
        print(
            f"| managers (simulated) | {base['waste']:.2%} | {base['stockout']:.2%} | - | {base['lost_units']:,.0f} | {base['margin']:.2%} | - |"
        )
        greens_ids = set(panel.loc[panel["category"] == "Leafy greens", "sku_id"].astype(str))
        for floor in args.floors or (0.9, 0.93, 0.95, 0.97, 0.98):
            trial = ReplayParams(**{**params.__dict__, "service_floor": floor})
            res = replay(
                panel, forecasts, share, trial, dp.validate_from, dp.validate_to, "reallocate_trim"
            )
            m = summarise(res)
            g = summarise(res[res["sku_id"].isin(greens_ids)])
            trimmed = 1 - m["delivered"] / base["delivered"]
            print(
                f"| {floor} | {m['waste']:.2%} | {m['stockout']:.2%} | {g['stockout']:.2%} | {m['lost_units']:,.0f} | {m['margin']:.2%} | {trimmed:+.1%} |"
            )
        return
    results = {
        s: replay(panel, forecasts, share, params, dp.validate_from, dp.validate_to, s)
        for s in SCENARIOS
    }
    cat = panel[["sku_id", "category"]].drop_duplicates().set_index("sku_id")["category"]
    fmt = panel[["store_id", "format"]].drop_duplicates().set_index("store_id")["format"]

    print("| Scenario | Waste | Stock-outs | Lost units | Gross margin | Units delivered |")
    print("|---|---|---|---|---|---|")
    base = summarise(results["managers"])
    for s in SCENARIOS:
        m = summarise(results[s])
        print(
            f"| {LABEL[s]} | {m['waste']:.2%} | {m['stockout']:.2%} | {m['lost_units']:,.0f} | "
            f"{m['margin']:.2%} | {m['delivered']:,.0f} |"
        )

    print(
        "\nChange against the managers' split, by category (waste pts / stock-out pts / margin pts)"
    )
    for name, frame_key in (("category", cat), ("store type", fmt)):
        print(f"\n{name}:")
        for value in sorted(set(frame_key.values)):
            line = [f"  {value:13s}"]
            for s in ("reallocate", "reallocate_trim"):
                key = "sku_id" if name == "category" else "store_id"
                sel_b = results["managers"][results["managers"][key].map(frame_key) == value]
                sel_s = results[s][results[s][key].map(frame_key) == value]
                b, m = summarise(sel_b), summarise(sel_s)
                line.append(
                    f"{LABEL[s][:22]:22s} {100 * (m['waste'] - b['waste']):+.2f} / {100 * (m['stockout'] - b['stockout']):+.2f} / {100 * (m['margin'] - b['margin']):+.2f}"
                )
            print("  |  ".join(line))

    trim = results["reallocate_trim"]
    day = (
        trim[trim["in_season"]]
        .groupby(["date", "sku_id"])
        .agg(delivered=("delivered", "sum"), committed=("committed_sku_day", "first"))
    )
    short = (day["delivered"] + 1e-6 < day["committed"]).sum()
    pool = results["managers"][results["managers"]["in_season"]]["delivered"].sum()
    print(
        f"\nfarmer groups: committed volume is unchanged by construction; sku-days where we delivered less than the "
        f"committed volume: {short} (must be 0)"
    )
    print(
        f"spot (mandi) volume trimmed under the trim scenario: {pool - trim[trim['in_season']]['delivered'].sum():,.0f} units "
        f"({(pool - trim[trim['in_season']]['delivered'].sum()) / pool:.1%} of the supply)"
    )
    print(
        f"farmer-group share of the supply: {day['committed'].sum() / pool:.1%} actual -> "
        f"{day['committed'].sum() / trim[trim['in_season']]['delivered'].sum():.1%} with trimming"
    )
    _ = base


if __name__ == "__main__":
    main()
