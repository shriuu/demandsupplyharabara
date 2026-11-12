"""Tune the demand model's few settings on rolling training windows. The holdout is never read.

Median forecast only (the likely value; WAPE against units sold is the brief's measure), so each
trial is one fit instead of three. Stage 1 changes one setting at a time from the current values on
windows A and B. Stage 2 combines the winners and confirms on window C, which stage 1 never used.
Ranges are not calibrated here: compare settings with each other, not with docs/final_results.md.

    uv run python scripts/tune_demand.py [--fast]
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from harabhara.data.prepare import build_examples, build_panel
from harabhara.features.build import CATEGORICAL, feature_columns
from harabhara.models.cold_start import apply_thin_history
from harabhara.settings import load_config
from harabhara.sim.metrics import bias, wape

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "work" / "PS-10_store_sales_daily.xlsx"
EXTERNAL = ROOT / "work" / "PS-10_external_factors.xlsx"

# (name, fit until, validate from, validate to). All inside the training period.
WINDOWS = {
    "A": (date(2026, 6, 9), date(2026, 6, 10), date(2026, 8, 5)),
    "B": (date(2025, 12, 31), date(2026, 1, 1), date(2026, 4, 30)),
    "C": (date(2026, 4, 30), date(2026, 5, 1), date(2026, 6, 9)),  # confirmation only
}


@dataclass(frozen=True)
class Setting:
    iterations: int = 1200
    depth: int = 6
    learning_rate: float = 0.06
    l2_leaf_reg: float = 3.0
    half_life_days: int | None = None  # None: every day counts the same

    def label(self) -> str:
        recency = (
            f", recent days weigh more (half-life {self.half_life_days}d)"
            if self.half_life_days
            else ""
        )
        return (
            f"{self.iterations} trees, depth {self.depth}, rate {self.learning_rate}, "
            f"l2 {self.l2_leaf_reg:g}{recency}"
        )


def fit_median(train: pd.DataFrame, cols: list[str], s: Setting, seed: int) -> CatBoostRegressor:
    cats = [c for c in CATEGORICAL if c in cols]
    weight = None
    if s.half_life_days:
        age = (train["target_date"].max() - train["target_date"]).dt.days.to_numpy()
        weight = 0.5 ** (age / s.half_life_days)
    model = CatBoostRegressor(
        loss_function="Quantile:alpha=0.5",
        iterations=s.iterations,
        depth=s.depth,
        learning_rate=s.learning_rate,
        l2_leaf_reg=s.l2_leaf_reg,
        random_seed=seed,
        verbose=False,
        allow_writing_files=False,
        cat_features=cats,
    )
    model.fit(train[cols], train["y_demand"], sample_weight=weight)
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="few trees (smoke test)")
    args = ap.parse_args()

    cfg = load_config()
    p = cfg.modeling.demand
    started = time.time()
    panel, _ = build_panel(SALES, EXTERNAL, cfg)
    ex = build_examples(panel, cfg)
    usable = (
        (ex["t_usable"] == 1)
        & (ex["t_in_season"] == 1)
        & ex["y_demand"].notna()
        & (ex["t_split"] == "train")
    )
    cols = feature_columns(ex)
    base = Setting(p.iterations, p.depth, p.learning_rate)
    if args.fast:
        base = replace(base, iterations=40)

    def score(s: Setting, window: str) -> tuple[float, float]:
        fit_until, v_from, v_to = WINDOWS[window]
        train = ex[usable & (ex["target_date"] <= pd.Timestamp(fit_until))]
        valid = ex[
            usable
            & (ex["target_date"] >= pd.Timestamp(v_from))
            & (ex["target_date"] <= pd.Timestamp(v_to))
        ].copy()
        assert not (valid["t_split"] == "holdout").any()
        model = fit_median(train, cols, s, p.seed)
        likely = np.clip(model.predict(valid[cols]), 0, None)
        raw = pd.DataFrame({"low": likely, "likely": likely, "high": likely}, index=valid.index)
        unseen = ~valid["sku_id"].astype(str).isin(set(train["sku_id"].astype(str)))
        out = apply_thin_history(raw, valid, p.min_history_days, p.thin_history_range_width, unseen)
        keep = out["likely"].notna()
        return (
            wape(out.loc[keep, "likely"], valid.loc[keep, "y_sold"]),
            bias(out.loc[keep, "likely"], valid.loc[keep, "y_sold"]),
        )

    trials: dict[str, Setting] = {"current": base}
    for depth in (4, 8):
        trials[f"depth {depth}"] = replace(base, depth=depth)
    for l2 in (10.0, 30.0):
        trials[f"l2 {l2:g}"] = replace(base, l2_leaf_reg=l2)
    trials["600 trees, rate 0.12"] = replace(
        base, iterations=max(base.iterations // 2, 1), learning_rate=0.12
    )
    trials["2400 trees, rate 0.03"] = replace(
        base, iterations=base.iterations * 2, learning_rate=0.03
    )
    for half in (60, 180):
        trials[f"recent days weigh more, half-life {half}d"] = replace(base, half_life_days=half)

    rows: dict[str, dict[str, float]] = {}
    for name, s in trials.items():
        res = {w: score(s, w) for w in ("A", "B")}
        rows[name] = {
            "A": res["A"][0], "B": res["B"][0],
            "mean": (res["A"][0] + res["B"][0]) / 2,
            "bias_A": res["A"][1], "bias_B": res["B"][1],
        }  # fmt: skip
        print(
            f"  {name}: A {res['A'][0]:.2%}  B {res['B'][0]:.2%}  ({time.time() - started:.0f}s)",
            flush=True,
        )

    print("\n## Stage 1: one change at a time (WAPE vs units sold, median forecast)")
    print("| Setting changed | Window A | Window B | Mean | vs current |")
    print("|---|---|---|---|---|")
    cur = rows["current"]["mean"]
    for name, r in rows.items():
        print(
            f"| {name} | {r['A']:.2%} | {r['B']:.2%} | {r['mean']:.2%} | {(r['mean'] - cur) * 100:+.2f} pts |"
        )

    # Stage 2: take every change that helped on BOTH windows, combine, confirm on window C.
    best = base
    for name, s in trials.items():
        if name == "current":
            continue
        if rows[name]["A"] < rows["current"]["A"] and rows[name]["B"] < rows["current"]["B"]:
            best = replace(
                best,
                **{
                    k: getattr(s, k)
                    for k in (
                        "iterations",
                        "depth",
                        "learning_rate",
                        "l2_leaf_reg",
                        "half_life_days",
                    )
                    if getattr(s, k) != getattr(base, k)
                },
            )
    print(f"\nCombined setting: {best.label()}")
    print("\n## Stage 2: combined setting against current, all three windows")
    print("| | Window A | Window B | Window C (not used to choose) |")
    print("|---|---|---|---|")
    for name, s in (("current", base), ("combined", best)):
        r = {w: score(s, w) for w in ("A", "B", "C")}
        print(
            f"| {name} | {r['A'][0]:.2%} | {r['B'][0]:.2%} | {r['C'][0]:.2%} (bias {r['C'][1]:+.1%}) |",
            flush=True,
        )
    print(f"\ntotal time {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
