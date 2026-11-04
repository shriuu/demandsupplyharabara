"""Run the nightly pipeline for one as-of day and write what the API loads.

For as-of day A (its evening):
- the demand model is fit on data up to A-1, and the range is calibrated on the four weeks before;
- evening orders are for A+1, from forecasts made on A and the stock left at A's close;
- morning alerts are for A, from forecasts made on A-1 and the stock after A's delivery;
- every suggestion goes through the rules engine; blocked ones are listed, never shown.
No outcome dated after A is read. See docs/pipeline.md for the demo-day mapping.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from harabhara.contracts import (
    FarmerVolumeForecast,
    Forecast,
    Projection,
    Range,
    Scorecard,
    Suggestion,
)
from harabhara.decisions.builder import (
    MorningStore,
    OrderInputs,
    Provenance,
    Series,
    build_morning,
    build_order,
)
from harabhara.pipeline.forecast import Forecaster, fit_forecaster, predict_origin, to_forecasts
from harabhara.pipeline.inputs import (
    PackData,
    fpo_for_sku,
    fpo_share_by_sku,
    last_training_day,
    life_days,
    load_pack,
    transfer_pairs,
    unit_cost_by_sku,
)
from harabhara.reasons.writer import Names, load_templates
from harabhara.rules.engine import Blocked, RulesEngine
from harabhara.rules.guardrails import Facts
from harabhara.settings import load_config
from harabhara.sim.replay import ReplayParams, warm_up
from harabhara.sim.scorecard import together
from harabhara.state.projection import Lot, project


@dataclass
class Outputs:
    forecasts: list[Forecast] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    blocked: list[Blocked] = field(default_factory=list)
    farmer: list[FarmerVolumeForecast] = field(default_factory=list)
    scorecards: list[Scorecard] = field(default_factory=list)
    trimming: list[dict[str, Any]] = field(default_factory=list)
    projections: list[Projection] = field(default_factory=list)


def _tz(pack: PackData) -> ZoneInfo:
    return ZoneInfo(pack.cfg.schedule.timezone)


def _replay_params(pack: PackData, upto: date) -> ReplayParams:
    cfg = pack.cfg
    return ReplayParams(
        life_days=life_days(pack.rules),
        unit_cost=unit_cost_by_sku(pack.purchases, upto),
        markdown_pct=cfg.rules.markdown.step_1_pct,
        sales_order=cfg.modeling.projection.sales_order,
        quantiles=cfg.modeling.demand.quantiles,
        allocation_steps=cfg.modeling.decisions.allocation_steps,
        waste_exponent=cfg.modeling.decisions.waste_weight_exponent,
        basket_allowance=cfg.costs.basket_allowance_per_lost_sale_inr,
        service_floor=cfg.modeling.decisions.service_level_floor,
    )


def _series_table(pack: PackData, day: date, params: ReplayParams) -> dict[tuple[str, str], Series]:
    """One ``Series`` per store and product that is in season on ``day``."""
    stores = pack.stores.set_index("store_id")
    skus = pack.skus.set_index("sku_id")
    today = pack.panel[(pack.panel["date"] == pd.Timestamp(day)) & pack.panel["in_season"]]
    table: dict[tuple[str, str], Series] = {}
    for row in today.to_dict("records"):
        store, sku = str(row["store_id"]), str(row["sku_id"])
        table[(store, sku)] = Series(
            store_id=store,
            sku_id=sku,
            category=str(skus.loc[sku, "category"]),
            product=str(skus.loc[sku, "sku_name"]),
            unit=str(skus.loc[sku, "selling_unit"]),
            format=str(stores.loc[store, "format"]),
            price=float(row["selling_price"]),
            unit_cost=params.unit_cost[sku],
            life_days=params.life_days[sku],
            festival_sensitive=bool(skus.loc[sku, "festival_sensitive"]),
        )
    return table


def _names(pack: PackData, series: Series) -> Names:
    return Names(
        product=series.product.lower(),
        unit=series.unit,
        stores={str(k): str(v) for k, v in pack.stores.set_index("store_id")["locality"].items()},
        buyers=pack.buyer_names,
    )


def _store_open(pack: PackData, fmt: str) -> str:
    hours = pack.cfg.schedule.store_hours
    return hours.Store.open if fmt == "Store" else hours.Dark_store.open


def _lots(state: list[list[float]]) -> tuple[Lot, ...]:
    return tuple(Lot(units, int(life)) for units, life in state if units > 0 and life >= 1)


def scorecards(pack: PackData, upto: date, share: dict[str, float]) -> list[Scorecard]:
    """Recorded waste, stock-outs and farmer share, chain-wide and per store (guardrail 4)."""
    days = pack.cfg.modeling.pipeline.scorecard_days
    start = upto - timedelta(days=days - 1)
    rows = pack.panel[
        (pack.panel["date"] >= pd.Timestamp(start))
        & (pack.panel["date"] <= pd.Timestamp(upto))
        & pack.panel["usable_for_targets"]
    ]
    weights = rows.groupby("sku_id")["received_units"].sum()
    farmer = float(sum(weights.get(sku, 0.0) * s for sku, s in share.items()) / weights.sum())
    definition = (
        "Share of purchased volume that came from farmer groups over the same days; "
        "a chain-wide figure, because purchases are not recorded per store."
    )

    def card(scope: str, frame: pd.DataFrame) -> Scorecard:
        return together(
            scope=scope,
            period_start=start,
            period_end=upto,
            waste_pct=float(100 * frame["wastage_units"].sum() / frame["received_units"].sum()),
            stockout_pct=float(100 * frame["stockout_flag"].mean()),
            farmer_share=farmer,
            farmer_share_definition=definition,
        )

    cards = [card("chain", rows)]
    cards += [card(str(s), g) for s, g in rows.groupby("store_id")]
    return cards


def farmer_forecasts(
    pack: PackData, origin_rows: pd.DataFrame, share: dict[str, float]
) -> list[FarmerVolumeForecast]:
    """Volume each farmer group should expect over the next three days: an estimate only."""
    by_sku = fpo_for_sku(pack.fpo)
    totals = (
        origin_rows.groupby(["sku_id", "target_date"])[["low", "likely", "high"]]
        .sum()
        .reset_index()
    )
    result: list[FarmerVolumeForecast] = []
    for row in totals.to_dict("records"):
        sku = str(row["sku_id"])
        fpo = by_sku.get(sku)
        if fpo is None:
            continue
        f = share.get(sku, 0.0)
        result.append(
            FarmerVolumeForecast(
                fpo_id=fpo,
                sku_id=sku,
                on=pd.Timestamp(row["target_date"]).date(),
                volume=Range(low=row["low"] * f, likely=row["likely"] * f, high=row["high"] * f),
            )
        )
    return result


def trimming_advice(
    pack: PackData,
    day: date,
    asks: dict[str, float],
    share: dict[str, float],
) -> list[dict[str, Any]]:
    """Spot-first trimming advice for tomorrow's purchase (guardrail 3: spot buying only)."""
    templates = load_templates()["trimming"]
    cfg = pack.cfg
    today = pack.panel[(pack.panel["date"] == pd.Timestamp(day)) & pack.panel["in_season"]]
    ordered = today.groupby("sku_id")["order_placed_for_tomorrow"].sum()
    unit_of = {str(k): str(v) for k, v in pack.skus.set_index("sku_id")["selling_unit"].items()}
    advice: list[dict[str, Any]] = []
    for sku, managers in ordered.items():
        committed = float(managers) * share.get(str(sku), 0.0)
        needed = max(committed, asks.get(str(sku), 0.0))
        trim = float(managers) - needed
        if trim < cfg.modeling.decisions.alert_min_units:
            continue
        advice.append(
            {
                "on": day + timedelta(days=1),
                "sku_id": str(sku),
                "spot_units_to_trim": round(trim),
                "reason": templates.format(
                    managers=round(float(managers)),
                    unit=unit_of[str(sku)],
                    asks=round(asks.get(str(sku), 0.0)),
                    committed=round(committed),
                    trim=round(trim),
                )
                + ".",
            }
        )
    return advice


def build_outputs(pack: PackData, fc: Forecaster, day: date) -> Outputs:
    cfg = pack.cfg
    tz = _tz(pack)
    params = _replay_params(pack, day)
    series = _series_table(pack, day, params)
    prov = Provenance(fc.model_version, pack.snapshot_id, cfg.digest)
    engine = RulesEngine(cfg)
    out = Outputs()

    prev = predict_origin(fc, pack, day - timedelta(days=1))  # morning view: targets day..day+2
    tonight = predict_origin(fc, pack, day)  # evening view: targets day+1..day+3
    out.forecasts = to_forecasts(tonight, fc, pack.snapshot_id)

    recorded = {
        (str(r["store_id"]), str(r["sku_id"])): float(r["order_placed_for_tomorrow"])
        for r in pack.panel[pack.panel["date"] == pd.Timestamp(day)].to_dict("records")
    }  # what the managers actually ordered for tomorrow, recorded on the as-of day
    state_prev = warm_up(pack.panel, day, params)  # shelves at the close of day-1
    state_close = warm_up(pack.panel, day + timedelta(days=1), params)  # at the close of day
    hot_c = float(pack.panel.loc[pack.panel["split"] == "train", "max_temp_c"].quantile(0.9))
    items: list[tuple[Suggestion, Facts]] = []

    # --- evening orders for day+1
    asks: dict[str, float] = {}
    first_night = tonight[tonight["horizon"] == 1]
    evening_now = datetime.combine(day, time(20, 30), tzinfo=tz)
    for row in first_night.to_dict("records"):
        key = (str(row["store_id"]), str(row["sku_id"]))
        s = series.get(key)
        if s is None:
            continue
        shelf = state_close.get(key, [])
        stock = sum(u for u, _ in shelf)
        order = build_order(
            OrderInputs(
                series=s,
                on=day + timedelta(days=1),
                demand=Range(low=row["low"], likely=row["likely"], high=row["high"]),
                stock=stock,
                manager_units=recorded.get(key),
                thin_history=bool(row["thin_history"]),
                weekend=bool(row["t_is_weekend"]),
                heavy_rain=bool(row["t_heavy_rain"]),
                festival_eve_intensity=float(row["t_eve_intensity"]),
                hot_day=float(row["t_max_temp_c"]) >= hot_c,
                sold_out_at_origin=bool(row["stocked_out_at_origin"]),
                last_day_stock=sum(u for u, life in shelf if life <= 1),
            ),
            cfg=cfg,
            names=_names(pack, s),
            prov=prov,
            now=evening_now,
        )
        if order is not None:
            items.append(order)
            asks[s.sku_id] = asks.get(s.sku_id, 0.0) + order[0].payload.recommended_units  # type: ignore[union-attr]

    # --- morning alerts for day
    morning_now = datetime.combine(day, time(7, 30), tzinfo=tz)
    pairs = transfer_pairs(pack.transfers, day)
    used: dict[str, float] = {}
    received = {
        (str(r["store_id"]), str(r["sku_id"])): float(r["received_units"])
        for r in pack.panel[pack.panel["date"] == pd.Timestamp(day)].to_dict("records")
    }
    forecast_for = {
        (str(r["store_id"]), str(r["sku_id"]), int(r["horizon"])): r
        for r in prev.to_dict("records")
    }
    for sku in sorted({k[1] for k in series}):
        stores: list[MorningStore] = []
        for (store, product), s in series.items():
            if product != sku:
                continue
            ranges = [forecast_for.get((store, sku, h)) for h in (1, 2, 3)]
            if any(r is None for r in ranges):
                continue
            on_shelf = _lots(state_prev.get((store, sku), []))
            delivered = received.get((store, sku), 0.0)
            if delivered > 0:
                on_shelf = (*on_shelf, Lot(delivered, s.life_days))
            demand = tuple(
                Range(low=r["low"], likely=r["likely"], high=r["high"]) for r in ranges if r
            )
            stores.append(
                MorningStore(
                    series=s,
                    lots=on_shelf,
                    demand=(demand[0], demand[1], demand[2]),
                    delivered_today=delivered,
                    thin_history=any(bool(r["thin_history"]) for r in ranges if r),
                    opening=_store_open(pack, s.format),
                )
            )
            out.projections.append(
                project(
                    store_id=store,
                    sku_id=sku,
                    as_of=day - timedelta(days=1),
                    opening=on_shelf,
                    deliveries=[None, None, None],
                    demand=list(demand),
                    sales_order=cfg.modeling.projection.sales_order,
                    assumptions=[
                        "lot ages are inferred from recorded deliveries (grade A shelf life)",
                        "shoppers take the freshest stock first",
                    ],
                    model_version=prov.model_version,
                    data_snapshot_id=prov.data_snapshot_id,
                    config_digest=prov.config_digest,
                )
            )
        if not stores:
            continue
        actions = build_morning(
            stores,
            as_of=day,
            now=morning_now,
            pairs=pairs,
            buyers=pack.buyers,
            used_capacity=used,
            names=_names(pack, stores[0].series),
            cfg=cfg,
            prov=prov,
        )
        for suggestion, _facts in actions:
            if suggestion.payload.kind == "surplus":
                used[suggestion.payload.buyer_id] = (
                    used.get(suggestion.payload.buyer_id, 0.0) + suggestion.payload.units
                )
        items.extend(actions)

    out.suggestions, out.blocked = engine.filter_suggestions(items)

    share = fpo_share_by_sku(pack.purchases, day, cfg.modeling.pipeline.farmer_share_days)
    out.farmer = farmer_forecasts(pack, tonight, share)
    out.scorecards = scorecards(pack, day, share)
    out.trimming = trimming_advice(pack, day, asks, share)
    return out


# ---- demo-day mapping and files ------------------------------------------------------------


def shift_to_today(
    out: Outputs, delta: timedelta, tag: str, now: datetime, keep_open_hours: float
) -> Outputs:
    """Show the as-of day as today. Dates move by ``delta``; no suggestion is already expired.

    Demo only. The content (weather, festival, stock) stays that of the data day; ids carry
    ``tag`` so a later load on another day does not collide with this one.
    """
    floor = now + timedelta(hours=keep_open_hours)
    shifted = Outputs(blocked=out.blocked)
    shifted.forecasts = [
        f.model_copy(update={"target_date": f.target_date + delta}) for f in out.forecasts
    ]
    for s in out.suggestions:
        deadline = max(s.deadline + delta, floor)
        shifted.suggestions.append(
            s.model_copy(
                update={
                    "id": f"{s.id}@{tag}",
                    "created_at": s.created_at + delta,
                    "deadline": deadline,
                }
            )
        )
    shifted.farmer = [f.model_copy(update={"on": f.on + delta}) for f in out.farmer]
    shifted.scorecards = [
        c.model_copy(
            update={"period_start": c.period_start + delta, "period_end": c.period_end + delta}
        )
        for c in out.scorecards
    ]
    shifted.trimming = [{**t, "on": t["on"] + delta} for t in out.trimming]
    shifted.projections = [
        p.model_copy(
            update={
                "as_of": p.as_of + delta,
                "days": [d.model_copy(update={"on": d.on + delta}) for d in p.days],
            }
        )
        for p in out.projections
    ]
    return shifted


def _dump(items: list[Any]) -> str:
    rows = [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]
    return json.dumps(rows, default=str, indent=1)


def write_outputs(out: Outputs, directory: Path) -> dict[str, int]:
    directory.mkdir(parents=True, exist_ok=True)
    files: dict[str, list[Any]] = {
        "forecasts.json": out.forecasts,
        "suggestions.json": out.suggestions,
        "farmer_forecasts.json": out.farmer,
        "scorecards.json": out.scorecards,
        "trimming.json": out.trimming,
        "projections.json": out.projections,
    }
    for name, items in files.items():
        (directory / name).write_text(_dump(items), encoding="utf-8")
    report = [
        {
            "id": b.suggestion.id,
            "rules": sorted({v.rule for v in b.violations}),
            "why": [v.message for v in b.violations],
        }
        for b in out.blocked
    ]
    (directory / "blocked.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return {name: len(items) for name, items in files.items()} | {"blocked.json": len(report)}


def check_not_holdout(day: date, last_training: date) -> None:
    """The holdout is read once, at the end: no run may start inside it."""
    if day > last_training:
        msg = f"{day} is inside the holdout; the holdout is read once, at the end"
        raise ValueError(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pipeline for one as-of day.")
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/run"))
    parser.add_argument("--as-of", type=date.fromisoformat, help="default: last training day")
    parser.add_argument("--demo-today", action="store_true", help="show the as-of day as today")
    args = parser.parse_args()

    cfg = load_config()
    pack = load_pack(args.work, cfg)
    day = args.as_of or last_training_day(pack.panel)
    try:
        check_not_holdout(day, last_training_day(pack.panel))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    fc = fit_forecaster(pack, day - timedelta(days=1))
    out = build_outputs(pack, fc, day)
    if args.demo_today:
        now = datetime.now(_tz(pack))
        out = shift_to_today(
            out,
            now.date() - day,
            f"demo{now:%Y%m%d}",
            now,
            cfg.modeling.pipeline.demo_keep_open_hours,
        )
    counts = write_outputs(out, args.out)
    print(f"as-of {day}; model {fc.model_version}; range shift {fc.shift:+.2f} units")
    for name, n in counts.items():
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
