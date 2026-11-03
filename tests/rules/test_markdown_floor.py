"""Playbook s5: never below purchase cost before the second-step hour."""

from __future__ import annotations

from harabhara.decisions.discount import plan_markdown
from harabhara.settings import load_config

RULES = load_config().rules.markdown


def _steps(price: float, cost: float, **over: object):  # type: ignore[no-untyped-def]
    base: dict[str, object] = {
        "sku_id": "P01",
        "category": "Vegetables",
        "price": price,
        "unit_cost": cost,
        "last_day_units": 30.0,
        "expected_unsold_last_day": 10.0,
        "second_day_units": 0.0,
        "expected_unsold_second_day": 0.0,
        "baseline_demand": 60.0,
        "opening": "07:00",
        "rules": RULES,
        "lift": 0.30,
        "earlier_min_share": 0.30,
    }
    return plan_markdown(**{**base, **over})  # type: ignore[arg-type]


def test_a_markdown_that_would_sell_below_cost_waits_for_the_evening_hour() -> None:
    (step,) = _steps(price=40.0, cost=35.0)  # 30% off = 28, below cost 35
    assert step.start == f"{RULES.step_2_after_hour:02d}:00"


def test_before_the_evening_hour_no_suggestion_sells_below_cost() -> None:
    for price, cost in [(40.0, 35.0), (40.0, 20.0), (13.0, 10.0), (100.0, 71.0)]:
        for step in _steps(price, cost):
            if step.start < f"{RULES.step_2_after_hour:02d}:00":
                assert step.price_after >= cost


def test_an_early_markdown_below_cost_is_not_suggested() -> None:
    early = _steps(
        price=40.0,
        cost=35.0,
        last_day_units=0.0,
        second_day_units=40.0,
        expected_unsold_second_day=30.0,
    )
    assert early == []
