"""Scorecards from what people recorded: all three measures together, never a guess."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from harabhara.contracts import OutcomeRecord
from harabhara.sim.recorded import scorecards_from_outcomes

TODAY = date(2026, 11, 10)
AT = datetime(2026, 11, 10, 22, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def closing(
    store: str, sku: str, sold: float, wasted: float, out: bool, days_ago: int = 0
) -> OutcomeRecord:
    return OutcomeRecord(
        kind="closing",
        on=TODAY - timedelta(days=days_ago),
        store_id=store,
        sku_id=sku,
        units_sold=sold,
        units_wasted=wasted,
        sold_out=out,
        recorded_by="m",
        recorded_at=AT,
    )


def bought(sku: str, units: float, source: str, days_ago: int = 0) -> OutcomeRecord:
    return OutcomeRecord(
        kind="purchase",
        on=TODAY - timedelta(days=days_ago),
        sku_id=sku,
        units_bought=units,
        source=source,
        recorded_by="d",
        recorded_at=AT,
    )


def test_nothing_recorded_gives_no_scorecard() -> None:
    assert scorecards_from_outcomes([], TODAY, 28) == []
    assert scorecards_from_outcomes([bought("t", 10, "spot")], TODAY, 28) == []


def test_waste_and_empty_shelves_per_store_and_for_the_chain() -> None:
    rows = [
        closing("S1", "t", sold=90, wasted=10, out=False),
        closing("S1", "b", sold=50, wasted=0, out=True),
        closing("S2", "t", sold=80, wasted=20, out=False),
    ]
    cards = {c.scope: c for c in scorecards_from_outcomes(rows, TODAY, 28)}
    assert set(cards) == {"chain", "S1", "S2"}
    assert cards["S1"].waste_pct == pytest.approx(100 * 10 / 150)
    assert cards["S1"].stockout_pct == pytest.approx(50.0)
    assert cards["S2"].stockout_pct == pytest.approx(0.0)
    assert cards["chain"].waste_pct == pytest.approx(100 * 30 / 250)
    assert cards["chain"].stockout_pct == pytest.approx(100 / 3)


def test_farmer_share_comes_from_purchases_or_says_why_it_is_unknown() -> None:
    sales = [closing("S1", "t", sold=90, wasted=10, out=False)]
    none = scorecards_from_outcomes(sales, TODAY, 28)[0]
    assert none.farmer_share is None
    assert none.farmer_share_definition
    buys = [bought("t", 30, "farmer_group"), bought("t", 70, "spot")]
    chain = next(c for c in scorecards_from_outcomes(sales + buys, TODAY, 28) if c.scope == "chain")
    assert chain.farmer_share == pytest.approx(0.30)
    store = next(c for c in scorecards_from_outcomes(sales + buys, TODAY, 28) if c.scope == "S1")
    assert store.farmer_share is None  # purchases are not recorded per store


def test_only_the_window_counts() -> None:
    rows = [closing("S1", "t", 90, 10, False), closing("S1", "t", 10, 90, True, days_ago=40)]
    card = scorecards_from_outcomes(rows, TODAY, 28)[0]
    assert card.waste_pct == pytest.approx(10.0)
    assert card.period_end == TODAY
    assert card.period_start == TODAY - timedelta(days=27)


def test_a_store_with_no_units_at_all_is_left_out() -> None:
    rows = [closing("S1", "t", 0, 0, False), closing("S2", "t", 10, 0, False)]
    assert {c.scope for c in scorecards_from_outcomes(rows, TODAY, 28)} == {"chain", "S2"}
