"""The final test (T01, T03, T10): forecast and replay the calendar's holdout, once.

    uv run python scripts/holdout_run.py --dry-run     # same code path on training dates
    uv run python scripts/holdout_run.py --holdout     # the real read; refuses a second time

The model is fit on data up to the last training day only, its range calibrated on the four
weeks before, with the settings frozen in ``config/``. Nothing is tuned after the first look.
Waste, empty shelves and farmer share are always reported together (guardrail 4).
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from harabhara.decisions.economics import unit_costs
from harabhara.pipeline.forecast import _predict_frame, fit_forecaster
from harabhara.pipeline.inputs import last_training_day, life_days, load_pack
from harabhara.settings import load_config
from harabhara.sim.evaluation import by_slice, score
from harabhara.sim.metrics import gross_margin
from harabhara.sim.replay import ReplayParams, Scenario, replay

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "artifacts" / "holdout_done.lock"
SCENARIOS: tuple[Scenario, ...] = ("managers", "reallocate_trim")
LABEL = {"managers": "Managers' split (simulated)", "reallocate_trim": "Our split, spot trimmed"}


def pct(x: float) -> str:
    return f"{x:.2%}"


def summarise(res: pd.DataFrame) -> dict[str, float]:
    live = res[res["in_season"]]
    delivered = float(live["delivered"].sum())
    return {
        "waste": float(live["binned"].sum() / delivered),
        "stockout": float((live["lost"] > 0).mean()),
        "margin": gross_margin(float(live["revenue"].sum()), float(live["cost"].sum())),
        "delivered": delivered,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--holdout", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    pack = load_pack(ROOT / "work", cfg)
    last_train = last_training_day(pack.panel)
    if args.holdout:
        if LOCK.exists():
            raise SystemExit(
                f"The holdout was already read ({LOCK.read_text().strip()}). Once only."
            )
        fit_until = last_train
        start, end = cfg.metrics.holdout.start, cfg.metrics.holdout.end
    else:
        end = last_train
        start = end - timedelta(days=cfg.metrics.holdout.days - 1)
        fit_until = start - timedelta(days=1)
    print(
        f"mode {'HOLDOUT' if args.holdout else 'dry run'}; fit until {fit_until}; window {start} to {end}"
    )

    forecaster = fit_forecaster(pack, fit_until)
    ex = pack.examples
    window = ex[
        (ex["horizon"] == 1)
        & (ex["target_date"] >= pd.Timestamp(start))
        & (ex["target_date"] <= pd.Timestamp(end))
        & (ex["t_in_season"] == 1)
    ].copy()
    if not args.holdout:
        assert not (window["t_split"] == "holdout").any(), "dry run must not touch the holdout"
    pred = _predict_frame(forecaster.model, window, forecaster.cfg, forecaster.shift)
    window["f_low"], window["f_likely"], window["f_high"] = (
        pred["low"],
        pred["likely"],
        pred["high"],
    )
    window["f_managers"] = window["sold_mean_7"]
    window = window.dropna(subset=["f_managers", "f_likely"])
    sold = window[window["t_usable"] == 1]

    out: list[str] = [
        f"# {'Holdout' if args.holdout else 'Dry run'} results ({start} to {end})",
        "",
    ]
    out += [
        "## T01: forecast error against units sold, same rows",
        "| Forecast | WAPE | Bias | Rows |",
        "|---|---|---|---|",
    ]
    for name, col in (("Model", "f_likely"), ("Managers' rule", "f_managers")):
        s = score(sold, col, "y_sold")
        out.append(f"| {name} | {s['wape']:.1%} | {s['bias']:+.1%} | {int(s['n']):,} |")
    inside = ((sold["y_sold"] >= sold["f_low"]) & (sold["y_sold"] <= sold["f_high"])).mean()
    out += ["", f"Share of outcomes inside the stated range: {inside:.1%}", ""]
    for col, title in (
        ("category", "category"),
        ("t_dow", "weekday"),
        ("t_heavy_rain", "heavy rain"),
    ):
        if col in sold.columns:
            table = by_slice(sold, col, {"Model": "f_likely", "Managers": "f_managers"}, "y_sold")
            out += [f"### By {title}", table.to_markdown(index=False), ""]

    # T03: festival eve uplift against the same product on ordinary days
    eve = sold[sold["t_eve_intensity"] > 0]
    if len(eve):
        out += [
            "## T03: festival eves, forecast against actual (ratio to the product's own ordinary days)"
        ]
        usual = sold[(sold["t_eve_intensity"] == 0) & (sold["t_festival_intensity"] == 0)]
        rows = []
        for sku, g in eve.groupby("sku_id"):
            base = usual[usual["sku_id"] == sku]
            if len(base) and base["y_sold"].mean() > 0 and base["f_likely"].mean() > 0:
                rows.append(
                    (
                        sku,
                        g["f_likely"].mean() / base["f_likely"].mean(),
                        g["y_sold"].mean() / base["y_sold"].mean(),
                    )
                )
        out += ["| Product | Forecast uplift | Actual uplift |", "|---|---|---|"]
        out += [f"| {s} | {f:.2f}x | {a:.2f}x |" for s, f, a in rows]
        out.append("")

    # T10: replay the window with the managers' split and ours
    panel = pack.panel
    purchases = pack.purchases
    costs = unit_costs(purchases[purchases["date"] <= pd.Timestamp(fit_until)])
    fpo = (
        purchases[purchases["source_type"] == "FPO contract"]
        .groupby(["date", "sku_id"])["quantity_units"]
        .sum()
    )
    total = purchases.groupby(["date", "sku_id"])["quantity_units"].sum()
    share = (fpo / total).fillna(0.0).reindex(total.index, fill_value=0.0)
    params = ReplayParams(
        life_days=life_days(pack.rules),
        unit_cost={str(k): float(v) for k, v in costs.items()},
        markdown_pct=cfg.rules.markdown.step_1_pct,
        sales_order=cfg.modeling.projection.sales_order,
        quantiles=cfg.modeling.demand.quantiles,
        allocation_steps=cfg.modeling.decisions.allocation_steps,
        waste_exponent=cfg.modeling.decisions.waste_weight_exponent,
        basket_allowance=cfg.costs.basket_allowance_per_lost_sale_inr,
        service_floor=cfg.modeling.decisions.service_level_floor,
    )
    forecasts = pred[["low", "likely", "high"]].set_index(
        pd.MultiIndex.from_frame(window[["store_id", "sku_id", "target_date"]])
    )
    results = {s: replay(panel, forecasts, share, params, start, end, s) for s in SCENARIOS}
    out += [
        "## T10: replay, waste / empty shelves / margin together",
        "| Scenario | Waste | Empty shelves | Gross margin |",
        "|---|---|---|---|",
    ]
    for s in SCENARIOS:
        m = summarise(results[s])
        out.append(
            f"| {LABEL[s]} | {pct(m['waste'])} | {pct(m['stockout'])} | {pct(m['margin'])} |"
        )
    trim, base = results["reallocate_trim"], results["managers"]
    day = (
        trim[trim["in_season"]]
        .groupby(["date", "sku_id"])
        .agg(delivered=("delivered", "sum"), committed=("committed_sku_day", "first"))
    )
    short = int((day["delivered"] + 1e-6 < day["committed"]).sum())
    pool = float(base[base["in_season"]]["delivered"].sum())
    out += [
        "",
        f"Farmer groups: committed volume unchanged; sku-days delivered below it: {short} (must be 0).",
        f"Farmer-group share of supply: {day['committed'].sum() / pool:.1%} actual, "
        f"{day['committed'].sum() / trim[trim['in_season']]['delivered'].sum():.1%} with spot trimming.",
        "",
        "By store type and category (change against the managers' split, in points: waste / empty shelves):",
    ]
    cat = panel[["sku_id", "category"]].drop_duplicates().set_index("sku_id")["category"]
    fmt = panel[["store_id", "format"]].drop_duplicates().set_index("store_id")["format"]
    for key, mapping, title in (("sku_id", cat, "category"), ("store_id", fmt, "store type")):
        out.append(f"\n{title}:")
        for value in sorted(set(mapping.values)):
            b = summarise(base[base[key].map(mapping) == value])
            m = summarise(trim[trim[key].map(mapping) == value])
            out.append(
                f"- {value}: {100 * (m['waste'] - b['waste']):+.2f} / {100 * (m['stockout'] - b['stockout']):+.2f}"
            )
    out += [
        "",
        "Limits: one data pack; demand does not respond to extra stock or to markdowns in the replay.",
    ]

    text = "\n".join(out) + "\n"
    target = ROOT / "docs" / ("final_results.md" if args.holdout else "holdout_dry_run.md")
    target.write_text(text, encoding="utf-8")
    if args.holdout:
        LOCK.parent.mkdir(exist_ok=True)
        LOCK.write_text(f"read on {date.today()}\n")
    print(text)


if __name__ == "__main__":
    main()
