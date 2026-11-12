"""What a graph shows for one day, and what an area manager might raise with a store manager.

Pure functions over closing counts. No model, no free text: each point is a code plus the numbers
behind it, so the screen can say it in the user's language and a manager can check it. Waste and
empty shelves are always looked at together (guardrail 4). Every threshold is in config.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from harabhara.api.schemas import SeriesPoint, SkuAmount, SkuCount, StoreDay, TalkCode, TalkPoint
from harabhara.contracts import OutcomeRecord
from harabhara.settings.schema import PipelineParams


@dataclass(frozen=True)
class TalkLimits:
    detail_items: int
    period_items: int
    waste_min_pct: float
    out_min_pct: float
    late_orders_days: int
    no_count_days: int
    store_gap_pts: float
    trend_pts: float
    max_points: int

    @classmethod
    def from_config(cls, p: PipelineParams) -> TalkLimits:
        return cls(
            p.chart_detail_items,
            p.chart_period_items,
            p.talk_waste_min_pct,
            p.talk_out_min_pct,
            p.talk_late_orders_days,
            p.talk_no_count_days,
            p.talk_store_gap_pts,
            p.talk_trend_pts,
            p.talk_max_points,
        )


# most important first; the list is cut at ``max_points``
_PRIORITY: list[TalkCode] = [
    "out_product",
    "store_out",
    "waste_product",
    "store_waste",
    "late_orders",
    "out_rising",
    "waste_rising",
    "no_counts",
    "improving",
]


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole > 0 else None


def day_detail(
    closed: list[OutcomeRecord], many_stores: bool, n: int
) -> tuple[list[SkuAmount], list[SkuCount], list[StoreDay]]:
    """Where a day's waste and empty shelves came from: products first, then stores."""
    wasted: dict[str, float] = defaultdict(float)
    ran_out: dict[str, int] = defaultdict(int)
    for r in closed:
        wasted[r.sku_id] += r.units_wasted or 0.0
        if r.sold_out:
            ran_out[r.sku_id] += 1
    top = sorted(((k, v) for k, v in wasted.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))[:n]
    out = sorted(ran_out.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    stores: list[StoreDay] = []
    if many_stores:
        by: dict[str, list[OutcomeRecord]] = defaultdict(list)
        for r in closed:
            if r.store_id:
                by[r.store_id].append(r)
        for sid, rows in by.items():
            sold = sum(r.units_sold or 0.0 for r in rows)
            lost = sum(r.units_wasted or 0.0 for r in rows)
            stores.append(
                StoreDay(
                    store_id=sid,
                    waste_pct=_pct(lost, sold + lost),
                    stockout_pct=_pct(sum(1 for r in rows if r.sold_out), len(rows)),
                )
            )
        stores.sort(key=lambda s: (-(s.stockout_pct or 0) - (s.waste_pct or 0), s.store_id))
        stores = stores[:n]
    return (
        [SkuAmount(sku_id=k, units=round(v, 1)) for k, v in top],
        [SkuCount(sku_id=k, stores=v) for k, v in out],
        stores,
    )


def _half_gap(values: list[float | None]) -> float | None:
    """Second half minus first half, over the days that have a value. None if too little."""
    have = [v for v in values if v is not None]
    if len(have) < 4:
        return None
    mid = len(have) // 2
    first, second = have[:mid], have[mid:]
    return sum(second) / len(second) - sum(first) / len(first)


def talking_points(
    points: list[SeriesPoint], closings: list[OutcomeRecord], lim: TalkLimits
) -> list[TalkPoint]:
    """Things worth raising, most important first. Empty days are gaps, never zeros."""
    out: list[TalkPoint] = []
    sold = sum(r.units_sold or 0.0 for r in closings)
    lost = sum(r.units_wasted or 0.0 for r in closings)
    overall_waste = _pct(lost, sold + lost)
    overall_out = _pct(sum(1 for r in closings if r.sold_out), len(closings))

    # products that keep running out, or keep being thrown away
    per_sku: dict[str, list[OutcomeRecord]] = defaultdict(list)
    for r in closings:
        per_sku[r.sku_id].append(r)
    out_rank = []
    waste_rank = []
    for sku, rows in per_sku.items():
        ran = sum(1 for r in rows if r.sold_out)
        out_share = _pct(ran, len(rows)) or 0.0
        if ran and out_share >= lim.out_min_pct:
            out_rank.append((ran, sku, out_share, len(rows)))
        s_units = sum(r.units_sold or 0.0 for r in rows)
        w_units = sum(r.units_wasted or 0.0 for r in rows)
        w_share = _pct(w_units, s_units + w_units) or 0.0
        if w_units > 0 and w_share >= lim.waste_min_pct:
            waste_rank.append((w_units, sku, w_share))
    if out_rank:
        ran, sku, share, rows_n = sorted(out_rank, key=lambda t: (-t[0], t[1]))[0]
        out.append(TalkPoint(code="out_product", sku_id=sku, value=share, n=ran, value2=rows_n))
    if waste_rank:
        units, sku, share = sorted(waste_rank, key=lambda t: (-t[0], t[1]))[0]
        out.append(TalkPoint(code="waste_product", sku_id=sku, value=share, value2=round(units, 1)))

    # a store far worse than the group (only when the graph covers several stores)
    per_store: dict[str, list[OutcomeRecord]] = defaultdict(list)
    for r in closings:
        if r.store_id:
            per_store[r.store_id].append(r)
    if len(per_store) > 1:
        worst_out: tuple[float, str] | None = None
        worst_waste: tuple[float, str] | None = None
        for sid, rows in per_store.items():
            o = _pct(sum(1 for r in rows if r.sold_out), len(rows)) or 0.0
            w = (
                _pct(
                    sum(r.units_wasted or 0.0 for r in rows),
                    sum((r.units_sold or 0.0) + (r.units_wasted or 0.0) for r in rows),
                )
                or 0.0
            )
            if (
                overall_out is not None
                and o - overall_out >= lim.store_gap_pts
                and (worst_out is None or o > worst_out[0])
            ):
                worst_out = (o, sid)
            if (
                overall_waste is not None
                and w - overall_waste >= lim.store_gap_pts
                and (worst_waste is None or w > worst_waste[0])
            ):
                worst_waste = (w, sid)
        if worst_out:
            out.append(TalkPoint(code="store_out", store_id=worst_out[1], value=worst_out[0]))
        if worst_waste:
            out.append(TalkPoint(code="store_waste", store_id=worst_waste[1], value=worst_waste[0]))

    # orders that ran out of time, and days nobody closed
    late_days = sum(1 for p in points if p.orders_expired > 0)
    if late_days >= lim.late_orders_days:
        out.append(
            TalkPoint(
                code="late_orders", n=late_days, value=float(sum(p.orders_expired for p in points))
            )
        )
    quiet = sum(1 for p in points if p.products_closed == 0)
    if quiet >= lim.no_count_days and quiet < len(points):
        out.append(TalkPoint(code="no_counts", n=quiet))

    # which way things are moving
    waste_gap = _half_gap([p.waste_pct for p in points])
    out_gap = _half_gap([p.stockout_pct for p in points])
    if out_gap is not None and out_gap >= lim.trend_pts:
        out.append(TalkPoint(code="out_rising", value=round(out_gap, 1)))
    if waste_gap is not None and waste_gap >= lim.trend_pts:
        out.append(TalkPoint(code="waste_rising", value=round(waste_gap, 1)))
    if (
        waste_gap is not None
        and out_gap is not None
        and waste_gap <= -lim.trend_pts
        and out_gap <= 0
    ):
        out.append(
            TalkPoint(code="improving", value=round(-waste_gap, 1), value2=round(out_gap, 1))
        )

    out.sort(key=lambda t: _PRIORITY.index(t.code))
    out = out[: lim.max_points]
    if not out and closings:
        return [TalkPoint(code="all_fine")]
    return out


def period_summary(closings: list[OutcomeRecord], n: int) -> tuple[list[SkuAmount], list[SkuCount]]:
    """Over a whole period: what was thrown away most, and what ran out most often.

    The second list counts closing counts where the product ran out (``stores`` holds that count).
    """
    wasted: dict[str, float] = defaultdict(float)
    ran: dict[str, int] = defaultdict(int)
    for r in closings:
        wasted[r.sku_id] += r.units_wasted or 0.0
        if r.sold_out:
            ran[r.sku_id] += 1
    top = sorted(((k, v) for k, v in wasted.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))[:n]
    most = sorted(ran.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    return (
        [SkuAmount(sku_id=k, units=round(v, 1)) for k, v in top],
        [SkuCount(sku_id=k, stores=v) for k, v in most],
    )
