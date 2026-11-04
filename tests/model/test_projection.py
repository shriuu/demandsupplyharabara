from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harabhara.contracts import Range
from harabhara.settings import load_config
from harabhara.state.projection import Lot, project, roll_forward

lots = st.builds(
    Lot,
    units=st.floats(min_value=0, max_value=500, allow_nan=False),
    life_left=st.integers(min_value=1, max_value=6),
)
orders = st.sampled_from(["freshest_first", "oldest_first"])


def test_stock_nobody_buys_is_binned_on_its_last_sellable_day() -> None:
    out = roll_forward([Lot(40, 1)], [None, None], [0, 0], "freshest_first")
    assert out[0].binned == 40
    assert out[0].closing_stock == 0


def test_a_lot_survives_until_its_last_day_then_is_binned() -> None:
    out = roll_forward([Lot(40, 3)], [None] * 3, [0, 0, 0], "freshest_first")
    assert [o.binned for o in out] == [0, 0, 40]


def test_shoppers_taking_the_freshest_leave_old_stock_to_expire() -> None:
    old, fresh = Lot(30, 1), Lot(30, 4)
    freshest = roll_forward([old, fresh], [None], [30], "freshest_first")[0]
    oldest = roll_forward([old, fresh], [None], [30], "oldest_first")[0]
    assert freshest.binned == 30  # old stock left behind
    assert oldest.binned == 0  # old stock sold first


def test_demand_above_stock_is_lost_sales() -> None:
    out = roll_forward([Lot(20, 3)], [None], [50], "freshest_first")[0]
    assert out.sold == 20
    assert out.lost_sales == 30


def test_a_delivery_arrives_before_the_day_sells() -> None:
    out = roll_forward([], [Lot(100, 2), None], [60, 60], "freshest_first")
    assert out[0].sold == 60
    assert out[1].sold == 40  # only what is left of the delivery
    assert out[1].lost_sales == 20
    assert out[1].binned == 0


def test_mismatched_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="same days"):
        roll_forward([], [None], [1, 2], "freshest_first")
    with pytest.raises(ValueError, match="no sellable days"):
        Lot(10, 0)


@given(
    opening=st.lists(lots, max_size=4),
    arrivals=st.lists(st.one_of(st.none(), lots), min_size=3, max_size=3),
    demand=st.lists(st.floats(min_value=0, max_value=400, allow_nan=False), min_size=3, max_size=3),
    order=orders,
)
def test_units_are_conserved(
    opening: list[Lot], arrivals: list[Lot | None], demand: list[float], order: str
) -> None:
    out = roll_forward(opening, arrivals, demand, order)  # type: ignore[arg-type]
    start = sum(lot.units for lot in opening)
    arriving = sum(lot.units for lot in arrivals if lot is not None)
    end = sum(o.sold + o.binned for o in out) + out[-1].closing_stock
    assert start + arriving == pytest.approx(end, abs=1e-6)
    for o in out:
        assert o.sold >= -1e-9
        assert o.lost_sales >= -1e-9
        assert o.binned >= -1e-9


@given(
    opening=st.lists(lots, max_size=4),
    base=st.lists(st.floats(min_value=0, max_value=200, allow_nan=False), min_size=3, max_size=3),
    order=orders,
)
def test_more_demand_never_means_more_waste(
    opening: list[Lot], base: list[float], order: str
) -> None:
    low = roll_forward(opening, [None] * 3, base, order)  # type: ignore[arg-type]
    high = roll_forward(opening, [None] * 3, [b + 25 for b in base], order)  # type: ignore[arg-type]
    assert sum(o.binned for o in high) <= sum(o.binned for o in low) + 1e-6
    assert sum(o.sold for o in high) >= sum(o.sold for o in low) - 1e-6


def test_projection_reports_ranges_with_likely_between() -> None:
    cfg = load_config()
    result = project(
        store_id="S01",
        sku_id="P13",
        as_of=date(2026, 11, 3),
        opening=[Lot(50, 2)],
        deliveries=[None, Lot(60, 2), None],
        demand=[Range(low=20, likely=40, high=70)] * 3,
        sales_order=cfg.modeling.projection.sales_order,
        assumptions=["lot ages inferred first-in first-out"],
        model_version="m",
        data_snapshot_id="d",
        config_digest=cfg.digest,
    )
    assert [d.day for d in result.days] == [1, 2, 3]
    assert result.days[0].on == date(2026, 11, 4)
    for day in result.days:
        for rng in (day.sold, day.lost_sales, day.expected_waste, day.closing_stock):
            assert rng.low <= rng.likely <= rng.high
    first = result.days[0]
    assert first.expected_waste.high >= first.expected_waste.low
    assert first.lost_sales.high > 0  # high demand outruns the 50 units on hand


def test_expected_value_weights_the_three_scenarios_by_swanson() -> None:
    from harabhara.state.projection import expected_value

    assert expected_value(Range(low=20, likely=30, high=40)) == pytest.approx(30.0)
    assert expected_value(Range(low=0, likely=0, high=100)) == pytest.approx(30.0)
    assert expected_value(Range(low=10, likely=10, high=10)) == pytest.approx(10.0)


def test_a_risk_only_in_the_tail_still_counts_in_the_expected_value() -> None:
    from harabhara.state.projection import expected_value

    tail = Range(low=0, likely=0, high=60)  # runs out only if demand is high
    assert tail.likely == 0
    assert expected_value(tail) == pytest.approx(18.0)
