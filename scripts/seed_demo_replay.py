"""Demo only. Replaces the closing counts of every store with the REPLAY result.

The replay re-runs real days as if our suggestions had been followed (same supply, our split,
spot buying trimmed, the chosen service floor). Counts written here are SIMULATED, not recorded,
and are signed ``demo-replay`` so they can be told apart. Development window only: the calendar's
holdout is never read.

    uv run python -m scripts.seed_demo_replay            # prints the result, writes nothing
    uv run python -m scripts.seed_demo_replay --apply    # writes to the live project
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from harabhara.api.firestore_store import FirestoreStorage
from harabhara.api.settings import from_env
from harabhara.contracts import OutcomeRecord
from harabhara.data.prepare import build_examples, build_panel
from harabhara.decisions.economics import unit_costs
from harabhara.features.build import feature_columns
from harabhara.jobs.daily import pick_data_day
from harabhara.models.cold_start import apply_thin_history
from harabhara.models.demand import DemandModel
from harabhara.pipeline.inputs import last_training_day, load_pack
from harabhara.settings import load_config
from harabhara.sim.replay import ReplayParams, replay

WORK = Path("work")
SALES, EXTERNAL = WORK / "PS-10_store_sales_daily.xlsx", WORK / "PS-10_external_factors.xlsx"
PROC = WORK / "PS-10_procurement_and_inventory.xlsx"
SEED = "demo-replay"
WORKERS = 16


def run_replay() -> pd.DataFrame:
    cfg = load_config()
    dp = cfg.modeling.demand
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
    model = DemandModel(dp).fit(train, feature_columns(examples))
    raw = model.predict(day1)
    adjusted = apply_thin_history(
        raw, day1, dp.min_history_days, dp.thin_history_range_width, model.unseen(day1)
    )
    forecasts = adjusted[["low", "likely", "high"]].set_index(
        pd.MultiIndex.from_frame(day1[["store_id", "sku_id", "target_date"]])
    )
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
        waste_exponent=cfg.modeling.decisions.waste_weight_exponent,
        basket_allowance=cfg.costs.basket_allowance_per_lost_sale_inr,
        service_floor=cfg.modeling.decisions.service_level_floor,
    )
    return replay(
        panel, forecasts, share, params, dp.validate_from, dp.validate_to, "reallocate_trim"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--days", type=int, default=29)
    args = ap.parse_args()
    cfg = load_config()
    res = run_replay()
    res = res[res["in_season"]]  # every store
    res["date"] = pd.to_datetime(res["date"]).dt.date
    for name, grp in [("S01", res[res.store_id == "S01"]), ("all stores", res)]:
        w = grp.binned.sum() / (grp.sold.sum() + grp.binned.sum())
        print(f"{name}: thrown away {w:.1%}, ran out {(grp.lost > 0).mean():.1%} (replay)")
    tz = ZoneInfo(cfg.schedule.timezone)
    today = datetime.now(tz).date()
    pack = load_pack(WORK, cfg)
    last = last_training_day(pack.panel)
    window = cfg.modeling.pipeline.daily_demo_window_days
    records: list[OutcomeRecord] = []
    for back in range(args.days, 0, -1):
        day = today - timedelta(days=back)
        data_day = pick_data_day(day, last, window)
        at = datetime(day.year, day.month, day.day, 22, 30, tzinfo=tz)
        for r in res[res["date"] == data_day].itertuples():
            records.append(
                OutcomeRecord(
                    kind="closing", on=day, store_id=str(r.store_id), sku_id=str(r.sku_id),
                    units_sold=round(float(r.sold)), units_wasted=round(float(r.binned)),
                    units_left=round(float(r.left)), sold_out=bool(r.lost > 0),
                    recorded_by=SEED, recorded_at=at,
                )
            )  # fmt: skip
    print(f"{len(records)} closing records for the last {args.days} days")
    if args.apply:
        storage = FirestoreStorage.from_project(from_env().firestore_project)
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(storage.put_outcome, records))
        print("written")
        from scripts.seed_demo_jayanagar import _decide

        tally: dict[str, int] = {}
        mine = [
            x
            for x in storage.list_suggestions(since=today - timedelta(days=args.days))
            if x.payload.kind == "order"
        ]
        with ThreadPoolExecutor(WORKERS) as pool:
            for what in pool.map(lambda x: _decide(storage, x, tz, True), mine):
                tally[what] = tally.get(what, 0) + 1
        print("order decisions, all stores:", tally)
    else:
        print("DRY RUN: nothing written")


if __name__ == "__main__":
    main()
