"""Replay history with a different split of the same supply (brief test T10, CLAUDE.md s10).

Three scenarios over the same days and the same demand:
- ``managers``: stores receive what they actually received (the simulator's baseline).
- ``reallocate``: the total delivered to all stores that day is unchanged (the purchase is
  committed); only the split across stores changes, using the forecast and stock on hand.
- ``reallocate_trim``: the total follows the stores' asks, but never falls below the committed
  farmer-group volume. Only mandi spot buying can shrink, and only as a suggestion (G03).

Forecasts used on day d are those made on the evening of d-1. Demand is the corrected demand;
the replay inherits the assumptions in docs/simulator.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

from harabhara.contracts import Range
from harabhara.decisions.allocation import StoreNeed, allocate
from harabhara.decisions.economics import critical_ratio, leftover_cost, lost_sale_cost
from harabhara.decisions.order import Quantiles, order_ask
from harabhara.state.projection import Lot, SalesOrder, StockState, step_day

Scenario = Literal["managers", "reallocate", "reallocate_trim"]


@dataclass(frozen=True)
class ReplayParams:
    life_days: Mapping[str, int]
    unit_cost: Mapping[str, float]
    markdown_pct: float
    sales_order: SalesOrder
    quantiles: Quantiles
    allocation_steps: int
    waste_exponent: float
    basket_allowance: float | None
    service_floor: float = 0.0


def warm_up(
    panel: pd.DataFrame, start: date, params: ReplayParams
) -> dict[tuple[str, str], StockState]:
    """Stock on every shelf at the start of the window, from the recorded deliveries."""
    state: dict[tuple[str, str], StockState] = {}
    before = panel[panel["date"] < pd.Timestamp(start)]
    for (store, sku), group in before.groupby(["store_id", "sku_id"], sort=False):
        stock: StockState = []
        life = int(params.life_days[str(sku)])
        for row in group.to_dict("records"):
            received = float(row["received_units"])
            demand = float(row["demand"]) if row["in_season"] and pd.notna(row["demand"]) else 0.0
            step_day(
                stock, Lot(received, life) if received > 0 else None, demand, params.sales_order
            )
        state[(str(store), str(sku))] = stock
    return state


def _forecast_map(forecasts: pd.DataFrame) -> dict[tuple[str, str, date], Range]:
    """(store, product, day) -> demand range, for forecasts that are complete."""
    result: dict[tuple[str, str, date], Range] = {}
    for key, row in zip(
        forecasts.index, forecasts[["low", "likely", "high"]].to_numpy(), strict=True
    ):
        if not pd.isna(row).any():
            store, sku, day = key
            result[(str(store), str(sku), pd.Timestamp(day).date())] = Range(
                low=float(row[0]), likely=float(row[1]), high=float(row[2])
            )
    return result


def replay(
    panel: pd.DataFrame,
    forecasts: pd.DataFrame,
    fpo_share: pd.Series,
    params: ReplayParams,
    start: date,
    end: date,
    scenario: Scenario,
) -> pd.DataFrame:
    """Results per store, product and day in ``[start, end]`` under one scenario.

    ``forecasts`` is indexed by (store_id, sku_id, target_date) with low, likely, high.
    ``fpo_share`` is indexed by (date, sku_id): the committed farmer-group share of the purchase.
    """
    state = warm_up(panel, start, params)
    ranges = _forecast_map(forecasts)
    share = {
        (pd.Timestamp(r["date"]).date(), str(r["sku_id"])): float(r["fpo_share"])
        for r in fpo_share.rename("fpo_share").reset_index().to_dict("records")
    }
    window = panel[(panel["date"] >= pd.Timestamp(start)) & (panel["date"] <= pd.Timestamp(end))]
    rows: list[dict[str, object]] = []
    for day_ts, today in window.groupby("date", sort=True):
        day = pd.Timestamp(str(day_ts)).date()
        for sku_key, group in today.groupby("sku_id", sort=False):
            sku = str(sku_key)
            life = int(params.life_days[sku])
            cost = float(params.unit_cost[sku])
            stores = {str(r["store_id"]): r for r in group.to_dict("records")}
            active = [s for s, r in stores.items() if bool(r["in_season"])]
            actual = {s: float(stores[s]["received_units"]) for s in stores}
            pool = sum(actual[s] for s in active)
            committed = pool * share.get((day, sku), 0.0)

            delivery = dict(actual)
            if scenario != "managers" and active and pool > 0:
                needs: list[StoreNeed] = []
                asked = 0.0
                for s in active:
                    demand = ranges.get((s, sku, day))
                    if demand is None:
                        needs = []
                        break
                    price = float(stores[s]["selling_price"])
                    held = sum(lot[0] for lot in state[(s, sku)])
                    sale = lost_sale_cost(price, cost, params.basket_allowance)
                    left = leftover_cost(cost, life, params.waste_exponent)
                    needs.append(StoreNeed(s, demand, held, sale, left))
                    ratio = max(critical_ratio(sale, left), params.service_floor)
                    asked += order_ask(demand, held, ratio, params.quantiles)
                if needs:
                    supply = pool if scenario == "reallocate" else max(committed, asked)
                    placed = allocate(supply, needs, params.quantiles, params.allocation_steps)
                    delivery = {s: placed.units.get(s, 0.0) for s in stores}
            for s, r in stores.items():
                in_season = bool(r["in_season"])
                give = delivery.get(s, 0.0) if in_season else 0.0
                wanted = float(r["demand"]) if in_season and pd.notna(r["demand"]) else 0.0
                lot = Lot(give, life) if give > 0 else None
                out = step_day(state[(s, sku)], lot, wanted, params.sales_order)
                price = float(r["selling_price"])
                markdown_price = price * (1 - params.markdown_pct / 100)
                rows.append(
                    {
                        "date": day,
                        "store_id": s,
                        "sku_id": sku,
                        "in_season": in_season,
                        "delivered": give,
                        "sold": out.sold,
                        "lost": out.lost_sales,
                        "binned": out.binned,
                        "revenue": (out.sold - out.sold_last_day) * price
                        + out.sold_last_day * markdown_price,
                        "cost": give * cost,
                        "committed_sku_day": committed,
                    }
                )
    return pd.DataFrame(rows)
