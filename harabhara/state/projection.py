"""Three-day stock roll-forward (CLAUDE.md s7 factor 6, s9).

Takes stock by age, expected deliveries and a demand range, and plays the next days forward:
shoppers buy, unsold stock gets a day older, and stock past its last sellable day is binned.
The same roll-forward drives the morning alerts and, later, the holdout replay, so it is
written once.

Units are conserved: opening stock plus deliveries equals sold plus binned plus closing stock.
The engine never lets a lot be sold past its last sellable day (guardrail G06).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from harabhara.contracts import Projection, ProjectionDay, Range

SalesOrder = Literal["freshest_first", "oldest_first"]


@dataclass(frozen=True)
class Lot:
    """Stock sharing one remaining life.

    ``life_left`` counts sellable days remaining including the day it is in. A lot with
    ``life_left == 1`` can be sold today and is binned at close.
    """

    units: float
    life_left: int

    def __post_init__(self) -> None:
        if self.units < 0:
            msg = "lot units cannot be negative"
            raise ValueError(msg)
        if self.life_left < 1:
            msg = "a lot with no sellable days left cannot be stock"
            raise ValueError(msg)


@dataclass(frozen=True)
class DayOutcome:
    sold: float
    lost_sales: float
    binned: float
    closing_stock: float
    sold_last_day: float = 0.0  # part of ``sold`` taken from stock on its last sellable day


StockState = list[list[float]]  # [units, life_left] per lot; mutated by step_day


def step_day(
    stock: StockState, delivery: Lot | None, wanted: float, sales_order: SalesOrder
) -> DayOutcome:
    """Play one day on ``stock`` (changed in place): delivery, selling, closing, ageing."""
    if delivery is not None and delivery.units > 0:
        stock.append([delivery.units, float(delivery.life_left)])
    stock.sort(key=lambda lot: lot[1], reverse=(sales_order == "freshest_first"))
    wanted = max(wanted, 0.0)
    remaining = wanted
    sold = 0.0
    sold_last_day = 0.0
    for lot in stock:
        take = min(lot[0], remaining)
        lot[0] -= take
        remaining -= take
        sold += take
        if lot[1] <= 1:
            sold_last_day += take
        if remaining <= 0:
            break
    binned = sum(lot[0] for lot in stock if lot[1] <= 1)
    stock[:] = [[lot[0], lot[1] - 1] for lot in stock if lot[1] > 1 and lot[0] > 0]
    return DayOutcome(
        sold=sold,
        lost_sales=wanted - sold,
        binned=binned,
        closing_stock=sum(lot[0] for lot in stock),
        sold_last_day=sold_last_day,
    )


def roll_forward(
    opening: Sequence[Lot],
    deliveries: Sequence[Lot | None],
    demand: Sequence[float],
    sales_order: SalesOrder,
) -> list[DayOutcome]:
    """Play ``len(demand)`` days. ``deliveries[d]`` arrives in the morning of day ``d``."""
    if len(deliveries) != len(demand):
        msg = "deliveries and demand must cover the same days"
        raise ValueError(msg)
    stock: StockState = [[lot.units, float(lot.life_left)] for lot in opening if lot.units > 0]
    return [
        step_day(stock, delivery, wanted, sales_order)
        for delivery, wanted in zip(deliveries, demand, strict=True)
    ]


def expected_value(outcome: Range) -> float:
    """The expected outcome from its low, likely and high values (Swanson's rule).

    The three scenarios are the 10th, 50th and 90th percentile of demand, and Swanson's rule
    weights them 0.3, 0.4 and 0.3. It matters for alerts: judging "will it run out" or "will it
    be left over" from the likely case alone hides real risk, because the risk sits in the
    tails. Outcomes move monotonically with demand, so the weights apply to the sorted range.
    """
    return 0.3 * outcome.low + 0.4 * outcome.likely + 0.3 * outcome.high


def _range(low: float, likely: float, high: float) -> Range:
    values = sorted((low, likely, high))
    return Range(low=values[0], likely=likely, high=values[2])


def project(
    *,
    store_id: str,
    sku_id: str,
    as_of: date,
    opening: Sequence[Lot],
    deliveries: Sequence[Lot | None],
    demand: Sequence[Range],
    sales_order: SalesOrder,
    assumptions: Sequence[str],
    model_version: str,
    data_snapshot_id: str,
    config_digest: str,
) -> Projection:
    """Roll the stock forward under low, likely and high demand and report each as a range.

    Outcomes move monotonically with demand (more demand means more sold and lost sales, less
    waste and less closing stock), so the likely outcome always sits between the other two.
    """
    runs = {
        name: roll_forward(opening, deliveries, [getattr(d, name) for d in demand], sales_order)
        for name in ("low", "likely", "high")
    }
    days: list[ProjectionDay] = []
    for index, day_demand in enumerate(demand):
        low, likely, high = (runs[name][index] for name in ("low", "likely", "high"))
        days.append(
            ProjectionDay(
                day=index + 1,
                on=as_of + timedelta(days=index + 1),
                demand=day_demand,
                sold=_range(low.sold, likely.sold, high.sold),
                lost_sales=_range(low.lost_sales, likely.lost_sales, high.lost_sales),
                expected_waste=_range(low.binned, likely.binned, high.binned),
                closing_stock=_range(low.closing_stock, likely.closing_stock, high.closing_stock),
            )
        )
    return Projection(
        store_id=store_id,
        sku_id=sku_id,
        as_of=as_of,
        days=days,
        assumptions=list(assumptions),
        model_version=model_version,
        data_snapshot_id=data_snapshot_id,
        config_digest=config_digest,
    )
