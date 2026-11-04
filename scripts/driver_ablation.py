"""Which inputs help? Drop one group at a time, add forecast-like weather noise, and refit weekly.

Training period only: the calendar's holdout is never read. For each variant it reports forecast
error and bias overall and for walk-in stores, dark stores, weekends and heavy-rain days, and
(for the main variants) what happens to waste and stock-outs when the supply is split with that
forecast. Ranges are not calibrated here, so compare variants with each other, not with
docs/replay.md. Usage:
    uv run python scripts/driver_ablation.py [--fast] [--temp-noise 2.0 --rain-noise 5.0]
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from harabhara.data.prepare import build_examples, build_panel
from harabhara.decisions.economics import unit_costs
from harabhara.features.build import feature_columns
from harabhara.models.cold_start import apply_thin_history
from harabhara.models.demand import DemandModel
from harabhara.settings import load_config
from harabhara.sim.metrics import bias, gross_margin, wape
from harabhara.sim.replay import ReplayParams, replay

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "work" / "PS-10_store_sales_daily.xlsx"
EXTERNAL = ROOT / "work" / "PS-10_external_factors.xlsx"
PROC = ROOT / "work" / "PS-10_procurement_and_inventory.xlsx"

GROUPS = {
    "weather": ["t_max_temp_c", "t_min_temp_c", "t_rainfall_mm", "t_humidity_pct", "t_heavy_rain"],
    "festival, payday, school holiday": [
        "t_festival_intensity", "t_eve_intensity", "t_after_intensity", "t_payday", "t_school_holiday",
    ],
    "weekday and weekend": ["t_dow", "t_is_weekend", "t_day_of_month"],
    "prices and promotions": [
        "shelf_price", "price_vs_recent", "promo_at_origin", "mandi_modal_price", "mandi_arrivals",
    ],
    "recent stock-outs": ["stockout_share_recent", "stocked_out_at_origin"],
}  # fmt: skip
HEAVY_RAIN_MM = 15.0  # the pack's own definition of a heavy-rain day (external README)


def predict(model: DemandModel, rows: pd.DataFrame, p) -> pd.DataFrame:  # type: ignore[no-untyped-def]
    raw = model.predict(rows)
    return apply_thin_history(
        raw, rows, p.min_history_days, p.thin_history_range_width, model.unseen(rows)
    )


def noisy_weather(rows: pd.DataFrame, temp_sd: float, rain_sd: float, seed: int) -> pd.DataFrame:
    """Weather as a forecast would give it: the truth plus an error. Applied to predictions only."""
    rng = np.random.default_rng(seed)
    out = rows.copy()
    n = len(out)
    out["t_max_temp_c"] = out["t_max_temp_c"] + rng.normal(0, temp_sd, n)
    out["t_min_temp_c"] = out["t_min_temp_c"] + rng.normal(0, temp_sd, n)
    out["t_rainfall_mm"] = (out["t_rainfall_mm"] + rng.normal(0, rain_sd, n)).clip(lower=0)
    out["t_heavy_rain"] = (out["t_rainfall_mm"] >= HEAVY_RAIN_MM).astype(int)
    return out


def metrics(frame: pd.DataFrame) -> dict[str, float]:
    honest = frame[frame["t_demand_estimated"] == 0]
    walk_in = frame[frame["format"] == "Store"]
    dark = frame[frame["format"] == "Dark store"]
    wk = frame[frame["t_is_weekend"] == 1]
    rain = frame[frame["t_heavy_rain"] == 1]
    return {
        "wape": wape(frame["f"], frame["y_sold"]),
        "bias": bias(frame["f"], frame["y_sold"]),
        "wape_honest": wape(honest["f"], honest["y_demand"]),
        "wape_walk_in": wape(walk_in["f"], walk_in["y_sold"]),
        "wape_dark": wape(dark["f"], dark["y_sold"]),
        "wape_weekend": wape(wk["f"], wk["y_sold"]),
        "wape_rain": wape(rain["f"], rain["y_sold"]) if len(rain) else float("nan"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="few trees and a short window (smoke test)")
    ap.add_argument("--temp-noise", type=float, default=2.0, help="ASSUMED forecast error, deg C")
    ap.add_argument("--rain-noise", type=float, default=5.0, help="ASSUMED forecast error, mm")
    ap.add_argument("--no-replay", action="store_true")
    ap.add_argument("--fit-until", type=date.fromisoformat)
    ap.add_argument("--validate-from", type=date.fromisoformat)
    ap.add_argument("--validate-to", type=date.fromisoformat)
    args = ap.parse_args()

    cfg = load_config()
    p = cfg.modeling.demand
    updates: dict[str, object] = {}
    if args.fast:
        updates = {"iterations": 40, "depth": 4, "validate_from": date(2026, 7, 15)}
    for name, value in (
        ("fit_until", args.fit_until),
        ("validate_from", args.validate_from),
        ("validate_to", args.validate_to),
    ):
        if value is not None:
            updates[name] = value
    p = p.model_copy(update=updates)

    started = time.time()
    panel, _ = build_panel(SALES, EXTERNAL, cfg)
    ex = build_examples(panel, cfg)
    fmt = panel[["store_id", "format"]].drop_duplicates().set_index("store_id")["format"]
    ex["format"] = ex["store_id"].map(fmt)
    usable = (
        (ex["t_usable"] == 1)
        & (ex["t_in_season"] == 1)
        & ex["y_demand"].notna()
        & (ex["t_split"] == "train")
    )
    end = pd.Timestamp(p.validate_to)
    v_start = pd.Timestamp(p.validate_from)
    train = ex[usable & (ex["target_date"] <= pd.Timestamp(p.fit_until))]
    valid = ex[usable & (ex["target_date"] >= v_start) & (ex["target_date"] <= end)].copy()
    assert not (valid["t_split"] == "holdout").any()
    cols_all = feature_columns(ex)
    print(
        f"window {v_start.date()} to {end.date()}; fit rows {len(train):,}; validation rows {len(valid):,}"
    )

    results: dict[str, pd.DataFrame] = {}

    def run(name: str, dropped: list[str] | None = None, noisy: bool = False) -> None:
        cols = [c for c in cols_all if c not in set(dropped or [])]
        model = DemandModel(p).fit(train, cols)
        rows = noisy_weather(valid, args.temp_noise, args.rain_noise, seed=0) if noisy else valid
        out = predict(model, rows, p)
        results[name] = valid.assign(f=out["likely"], low=out["low"], high=out["high"]).dropna(
            subset=["f"]
        )
        print(f"  fitted '{name}' ({time.time() - started:.0f}s elapsed)")

    run("full model")
    for group, cols in GROUPS.items():
        run(f"without {group}", dropped=cols)
    run("full model, weather with forecast-like error", noisy=True)

    # refit every week on all data known by then ("bit by bit")
    parts = []
    week = v_start
    while week <= end:
        stop = min(week + timedelta(days=6), end)
        known = ex[usable & (ex["target_date"] < week)]
        model = DemandModel(p).fit(known, cols_all)
        rows = valid[(valid["target_date"] >= week) & (valid["target_date"] <= stop)]
        out = predict(model, rows, p)
        parts.append(rows.assign(f=out["likely"], low=out["low"], high=out["high"]))
        week = stop + timedelta(days=1)
    results["full model, refit every week"] = pd.concat(parts).dropna(subset=["f"])
    print(f"  refit weekly done ({time.time() - started:.0f}s elapsed)")

    managers = valid.assign(f=valid["sold_mean_7"]).dropna(subset=["f"])
    results["managers' rule"] = managers
    common = set.intersection(
        *[
            set(map(tuple, r[["store_id", "sku_id", "target_date", "horizon"]].to_numpy()))
            for r in results.values()
        ]
    )
    key = ["store_id", "sku_id", "target_date", "horizon"]
    for name in results:
        keep = results[name][key].apply(tuple, axis=1).isin(common)
        results[name] = results[name][keep]

    table = pd.DataFrame({name: metrics(r) for name, r in results.items()}).T
    full = table.loc["full model"]
    print(
        f"\n## Forecast error on {len(results['full model']):,} identical rows (against units sold)"
    )
    print(
        "| Variant | WAPE | vs full | Bias | Walk-in stores | Dark stores | Weekends | Heavy-rain days |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for name, row in table.iterrows():
        delta = (row["wape"] - full["wape"]) * 100
        print(
            f"| {name} | {row['wape']:.1%} | {delta:+.2f} pts | {row['bias']:+.1%} | "
            f"{row['wape_walk_in']:.1%} | {row['wape_dark']:.1%} | {row['wape_weekend']:.1%} | {row['wape_rain']:.1%} |"
        )

    if args.no_replay:
        return
    purchases = pd.read_excel(PROC, sheet_name="purchases")
    purchases["date"] = pd.to_datetime(purchases["date"])
    costs = unit_costs(purchases[purchases["date"] <= pd.Timestamp(p.fit_until)])
    fpo = (
        purchases[purchases["source_type"] == "FPO contract"]
        .groupby(["date", "sku_id"])["quantity_units"]
        .sum()
    )
    total = purchases.groupby(["date", "sku_id"])["quantity_units"].sum()
    share = (fpo / total).fillna(0.0).reindex(total.index, fill_value=0.0)
    rules = pd.read_excel(PROC, sheet_name="shelf_life_rules").set_index("sku_id")
    params = ReplayParams(
        life_days={str(k): int(v) for k, v in rules["shelf_life_days_grade_A_ambient"].items()},
        unit_cost={str(k): float(v) for k, v in costs.items()},
        markdown_pct=cfg.rules.markdown.step_1_pct,
        sales_order=cfg.modeling.projection.sales_order,
        quantiles=p.quantiles,
        allocation_steps=cfg.modeling.decisions.allocation_steps,
        waste_exponent=cfg.modeling.decisions.waste_weight_exponent,
        basket_allowance=cfg.costs.basket_allowance_per_lost_sale_inr,
        service_floor=cfg.modeling.decisions.service_level_floor,
    )
    start_d, end_d = v_start.date(), end.date()

    def summarise(res: pd.DataFrame, only: str | None = None) -> dict[str, float]:
        live = res[res["in_season"]]
        if only:
            live = live[live["store_id"].map(fmt) == only]
        delivered = float(live["delivered"].sum())
        return {
            "waste": float(live["binned"].sum() / delivered),
            "stockout": float((live["lost"] > 0).mean()),
            "margin": gross_margin(float(live["revenue"].sum()), float(live["cost"].sum())),
        }

    base = replay(
        panel,
        pd.DataFrame(columns=["low", "likely", "high"]),
        share,
        params,
        start_d,
        end_d,
        "managers",
    )
    print(
        "\n## What the forecast does to waste and stock-outs (same supply split, spot buying trimmed)"
    )
    print(
        "| Variant | Waste | Stock-outs | Walk-in waste | Walk-in stock-outs | Dark waste | Dark stock-outs | Margin |"
    )
    print("|---|---|---|---|---|---|---|---|")
    b, bw, bd = summarise(base), summarise(base, "Store"), summarise(base, "Dark store")
    print(
        f"| managers' split (simulated) | {b['waste']:.2%} | {b['stockout']:.2%} | {bw['waste']:.2%} | {bw['stockout']:.2%} | {bd['waste']:.2%} | {bd['stockout']:.2%} | {b['margin']:.2%} |"
    )
    for name in [
        n
        for n in results
        if (n != "managers' rule" and "refit" not in n) or n == "full model, refit every week"
    ]:
        day1 = results[name][results[name]["horizon"] == 1]
        fc = day1[["low", "f", "high"]].rename(columns={"f": "likely"})[["low", "likely", "high"]]
        fc.index = pd.MultiIndex.from_frame(day1[["store_id", "sku_id", "target_date"]])
        res = replay(panel, fc, share, params, start_d, end_d, "reallocate_trim")
        s, sw, sd = summarise(res), summarise(res, "Store"), summarise(res, "Dark store")
        print(
            f"| {name} | {s['waste']:.2%} | {s['stockout']:.2%} | {sw['waste']:.2%} | {sw['stockout']:.2%} | {sd['waste']:.2%} | {sd['stockout']:.2%} | {s['margin']:.2%} |"
        )
    print(f"\ntotal time {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
