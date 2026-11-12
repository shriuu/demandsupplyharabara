"""What a graph says for a day, and what an area manager is told to raise. Pure rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from harabhara.api.schemas import SeriesPoint
from harabhara.api.talking import TalkLimits, day_detail, talking_points
from harabhara.contracts import OutcomeRecord
from tests.backend.conftest import NOW

LIM = TalkLimits(
    detail_items=2,
    waste_min_pct=10,
    out_min_pct=20,
    late_orders_days=2,
    no_count_days=2,
    store_gap_pts=5,
    trend_pts=2,
    max_points=4,
)
START = date(2026, 11, 1)
WHEN = datetime(2026, 11, 1, 22, 0, tzinfo=NOW.tzinfo)


def row(day: int, store: str, sku: str, sold: float, wasted: float, out: bool) -> OutcomeRecord:
    return OutcomeRecord(
        kind="closing", on=START + timedelta(days=day), store_id=store, sku_id=sku,
        units_sold=sold, units_wasted=wasted, sold_out=out, recorded_by="t", recorded_at=WHEN,
    )  # fmt: skip


def point(day: int, waste: float | None, out: float | None, expired: int = 0) -> SeriesPoint:
    return SeriesPoint(
        on=START + timedelta(days=day), units_sold=0, units_wasted=0, waste_pct=waste,
        stockout_pct=out, products_closed=0 if waste is None else 5, sold_out_products=0,
        orders_decided=0, orders_expired=expired, top_waste=[], ran_out=[], by_store=[],
    )  # fmt: skip


def codes(points: list[SeriesPoint], rows: list[OutcomeRecord]) -> list[str]:
    return [t.code for t in talking_points(points, rows, LIM)]


def test_a_day_names_what_was_thrown_away_what_ran_out_and_the_worst_stores() -> None:
    closed = [
        row(0, "S1", "tomato", 80, 20, False),
        row(0, "S1", "onion", 50, 0, True),
        row(0, "S2", "tomato", 90, 5, False),
        row(0, "S2", "onion", 40, 0, True),
        row(0, "S2", "okra", 10, 2, False),
    ]
    waste, ran_out, stores = day_detail(closed, many_stores=True, n=2)
    assert [(w.sku_id, w.units) for w in waste] == [("tomato", 25.0), ("okra", 2.0)]
    assert [(r.sku_id, r.stores) for r in ran_out] == [("onion", 2)]
    assert stores[0].store_id == "S1"  # worst first: waste and empty shelves together
    assert day_detail(closed, many_stores=False, n=2)[2] == []  # one store: no store list


def test_a_product_that_keeps_running_out_is_named_first() -> None:
    rows = [row(d, "S1", "tomato", 50, 0, d % 2 == 0) for d in range(6)]
    rows += [row(d, "S1", "onion", 50, 1, False) for d in range(6)]
    top = talking_points([point(d, 2, 50) for d in range(6)], rows, LIM)[0]
    assert (top.code, top.sku_id, top.n, top.value2) == ("out_product", "tomato", 3, 6)
    assert top.value == 50.0


def test_a_product_thrown_away_a_lot_is_named_and_a_small_one_is_not() -> None:
    rows = [row(d, "S1", "spinach", 40, 20, False) for d in range(4)]
    rows += [row(d, "S1", "onion", 99, 1, False) for d in range(4)]
    names = [
        (t.code, t.sku_id) for t in talking_points([point(d, 20, 0) for d in range(4)], rows, LIM)
    ]
    assert ("waste_product", "spinach") in names
    assert ("waste_product", "onion") not in names


def test_a_store_far_worse_than_the_group_is_named_for_the_group_graph_only() -> None:
    rows = [row(d, "S1", "tomato", 50, 0, True) for d in range(4)]
    rows += [row(d, s, "tomato", 50, 0, False) for d in range(4) for s in ("S2", "S3", "S4")]
    found = [
        t
        for t in talking_points([point(d, 0, 25) for d in range(4)], rows, LIM)
        if t.code == "store_out"
    ]
    assert [t.store_id for t in found] == ["S1"]
    solo = [row(d, "S1", "tomato", 50, 0, True) for d in range(4)]
    assert "store_out" not in codes([point(d, 0, 100) for d in range(4)], solo)


def test_orders_that_run_out_of_time_and_missing_counts_are_raised_only_when_repeated() -> None:
    rows = [row(0, "S1", "tomato", 50, 1, False)]
    one_late = [point(0, 2, 0, expired=3), point(1, 2, 0), point(2, None, None)]
    assert "late_orders" not in codes(one_late, rows)
    assert "no_counts" not in codes(one_late, rows)
    many = [
        point(0, 2, 0, expired=3),
        point(1, 2, 0, expired=1),
        point(2, None, None),
        point(3, None, None),
    ]
    got = {t.code: t for t in talking_points(many, rows, LIM)}
    assert got["late_orders"].n == 2
    assert got["late_orders"].value == 4
    assert got["no_counts"].n == 2


def test_a_worsening_trend_is_called_out_and_an_improvement_needs_shelves_not_worse() -> None:
    rows = [row(0, "S1", "tomato", 50, 1, False)]
    worse = [point(d, 4, 5 + 4 * d) for d in range(6)]
    assert "out_rising" in codes(worse, rows)
    better_but_emptier = [point(d, 12 - 2 * d, 10 + 5 * d) for d in range(6)]
    names = codes(better_but_emptier, rows)
    assert "improving" not in names  # waste fell, but shelves emptied: not an improvement
    assert "out_rising" in names
    better = [point(d, 12 - 2 * d, 10) for d in range(6)]
    imp = [t for t in talking_points(better, rows, LIM) if t.code == "improving"]
    assert imp
    assert (imp[0].value or 0) > 0
    assert imp[0].value2 == 0


def test_nothing_standing_out_says_so_and_no_data_says_nothing() -> None:
    rows = [row(d, "S1", "tomato", 100, 1, False) for d in range(6)]
    assert codes([point(d, 1, 0) for d in range(6)], rows) == ["all_fine"]
    assert codes([point(d, None, None) for d in range(6)], []) == []


def test_at_most_the_configured_number_of_points_most_important_first() -> None:
    rows = [row(d, "S1", "tomato", 50, 20, d < 4) for d in range(6)]
    rows += [row(d, s, "tomato", 50, 0, False) for d in range(6) for s in ("S2", "S3")]
    pts = [point(d, 10, 10 + 6 * d, expired=1) for d in range(6)]
    got = codes(pts, rows)
    assert len(got) <= LIM.max_points
    assert got[0] == "out_product"
