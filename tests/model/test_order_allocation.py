from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harabhara.contracts import Range
from harabhara.decisions.allocation import StoreNeed, allocate
from harabhara.decisions.economics import critical_ratio, leftover_cost, lost_sale_cost, unit_costs
from harabhara.decisions.order import cdf, order_ask, quantile_value

Q = (0.1, 0.5, 0.9)
D = Range(low=40, likely=60, high=90)

ranges = st.builds(
    lambda a, b, c: Range(low=a, likely=a + b, high=a + b + c),
    st.floats(1, 100),
    st.floats(0.5, 60),
    st.floats(0.5, 100),
)


def test_cdf_passes_through_the_three_forecast_points() -> None:
    assert cdf(D, 40, Q) == pytest.approx(0.1)
    assert cdf(D, 60, Q) == pytest.approx(0.5)
    assert cdf(D, 90, Q) == pytest.approx(0.9)
    assert cdf(D, 0, Q) == 0.0


@given(demand=ranges, q=st.floats(0.01, 0.97))
def test_quantile_and_cdf_are_inverses(demand: Range, q: float) -> None:
    assert cdf(demand, quantile_value(demand, q, Q), Q) == pytest.approx(q, abs=1e-6)


@given(demand=ranges, x=st.floats(0, 400), dx=st.floats(0, 100))
def test_cdf_never_decreases(demand: Range, x: float, dx: float) -> None:
    assert cdf(demand, x, Q) <= cdf(demand, x + dx, Q) + 1e-12


def test_an_order_covers_demand_less_what_is_on_hand() -> None:
    ratio = 0.5
    assert order_ask(D, 0, ratio, Q) == pytest.approx(60)
    assert order_ask(D, 25, ratio, Q) == pytest.approx(35)
    assert order_ask(D, 500, ratio, Q) == 0.0


def test_a_higher_cost_of_empty_shelves_orders_more() -> None:
    low = order_ask(D, 0, critical_ratio(5, 20), Q)
    high = order_ask(D, 0, critical_ratio(50, 5), Q)
    assert high > low


def test_short_life_products_order_less_than_long_life_ones() -> None:
    sale = lost_sale_cost(price=40, cost=25, allowance=None)
    short = critical_ratio(sale, leftover_cost(25, 1, 1.0))
    long_ = critical_ratio(sale, leftover_cost(25, 10, 1.0))
    assert short < long_


def test_the_basket_allowance_raises_the_cost_of_a_lost_sale() -> None:
    assert lost_sale_cost(40, 25, 10) == 25
    assert lost_sale_cost(40, 25, None) == 15


def test_unit_costs_are_quantity_weighted() -> None:
    import pandas as pd

    purchases = pd.DataFrame(
        {"sku_id": ["P01", "P01"], "quantity_units": [100, 300], "price_per_unit_inr": [20.0, 24.0]}
    )
    assert unit_costs(purchases)["P01"] == pytest.approx(23.0)


def _need(store: str, demand: Range, stock: float = 0.0) -> StoreNeed:
    return StoreNeed(store, demand, stock, lost_sale_cost=15.0, leftover_cost=25.0)


@given(
    pool=st.floats(0, 2000),
    demands=st.lists(ranges, min_size=1, max_size=6),
    stocks=st.lists(st.floats(0, 100), min_size=6, max_size=6),
)
def test_a_forced_allocation_places_every_unit_and_none_is_negative(
    pool: float, demands: list[Range], stocks: list[float]
) -> None:
    needs = [_need(f"S{i}", d, stocks[i]) for i, d in enumerate(demands)]
    result = allocate(pool, needs, Q, steps=100, force_all=True)
    assert sum(result.units.values()) + result.held_back == pytest.approx(pool, abs=1e-6)
    assert result.held_back == pytest.approx(0, abs=1e-6)
    assert all(v >= 0 for v in result.units.values())


def test_the_store_more_likely_to_run_out_gets_more() -> None:
    needs = [
        _need("busy", Range(low=80, likely=120, high=170)),
        _need("quiet", Range(low=10, likely=20, high=30)),
    ]
    result = allocate(100, needs, Q, steps=200)
    assert result.units["busy"] > result.units["quiet"]


def test_a_store_that_already_holds_enough_gets_little() -> None:
    needs = [_need("stocked", D, stock=200), _need("empty", D, stock=0)]
    result = allocate(60, needs, Q, steps=200)
    assert result.units["empty"] > result.units["stocked"]


def test_surplus_is_held_back_when_it_would_only_be_wasted() -> None:
    needs = [_need("a", Range(low=10, likely=15, high=20))]
    result = allocate(500, needs, Q, steps=200, force_all=False)
    assert result.held_back > 300
    assert result.units["a"] < 100


def test_a_negative_supply_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        allocate(-1, [_need("a", D)], Q, steps=10)
