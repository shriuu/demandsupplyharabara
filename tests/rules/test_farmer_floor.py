"""G02: never recommend paying a farmer group below its contract floor."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from harabhara.rules.guardrails import check_purchase_price


def test_a_price_below_the_floor_is_blocked() -> None:
    (violation,) = check_purchase_price(price=15.0, floor=15.7)
    assert violation.rule == "G02"


def test_a_price_at_or_above_the_floor_is_fine() -> None:
    assert check_purchase_price(price=15.7, floor=15.7) == []
    assert check_purchase_price(price=20.0, floor=15.7) == []


@given(price=st.floats(0, 500), floor=st.floats(0, 500))
def test_blocked_exactly_when_below_the_floor(price: float, floor: float) -> None:
    assert (check_purchase_price(price, floor) != []) == (price < floor)
