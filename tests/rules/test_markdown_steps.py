"""Playbook s5: 30% on the last sellable day from opening; 50% after 6 pm for greens and bananas."""

from __future__ import annotations

import pytest

from harabhara.decisions.discount import MarkdownProposal, plan_markdown
from harabhara.settings import load_config

RULES = load_config().rules.markdown


def _plan(**over: object) -> list[MarkdownProposal]:
    base: dict[str, object] = {
        "sku_id": "P01",
        "category": "Vegetables",
        "price": 40.0,
        "unit_cost": 20.0,
        "last_day_units": 30.0,
        "expected_unsold_last_day": 12.0,
        "second_day_units": 0.0,
        "expected_unsold_second_day": 0.0,
        "baseline_demand": 60.0,
        "opening": "07:00",
        "rules": RULES,
        "lift": 0.30,
        "earlier_min_share": 0.30,
    }
    return plan_markdown(**{**base, **over})  # type: ignore[arg-type]


def test_last_day_stock_is_marked_down_from_opening_by_the_playbook_step() -> None:
    (step,) = _plan()
    assert step.step_pct == RULES.step_1_pct
    assert step.start == "07:00"
    assert step.price_after == pytest.approx(40 * (1 - RULES.step_1_pct / 100))
    assert not step.earlier_than_last_day


def test_leafy_greens_get_a_second_step_after_the_evening_hour() -> None:
    steps = _plan(sku_id="P13", category="Leafy greens", price=13.0, unit_cost=6.0)
    assert [s.step_pct for s in steps] == [RULES.step_1_pct, RULES.step_2_pct]
    assert steps[1].start == f"{RULES.step_2_start_hour:02d}:00"


def test_bananas_get_the_second_step_but_tomatoes_do_not() -> None:
    banana = _plan(sku_id="P04", category="Fruits", price=56.0, unit_cost=25.0)
    assert len(banana) == 2
    assert len(_plan(sku_id="P01")) == 1


def test_nothing_is_suggested_when_there_is_no_last_day_stock() -> None:
    assert _plan(last_day_units=0.0) == []


def test_recovery_is_the_extra_units_the_markdown_can_sell_at_the_new_price() -> None:
    (step,) = _plan(expected_unsold_last_day=100.0, baseline_demand=60.0, lift=0.30)
    assert step.expected_recovery_inr == pytest.approx(
        18 * step.price_after
    )  # 60 * 0.30 extra units
    (small,) = _plan(expected_unsold_last_day=4.0)
    assert small.expected_recovery_inr == pytest.approx(4 * small.price_after)


def test_a_day_early_markdown_is_flagged_and_needs_enough_expected_waste() -> None:
    early = _plan(last_day_units=0.0, second_day_units=40.0, expected_unsold_second_day=20.0)
    assert len(early) == 1
    assert early[0].earlier_than_last_day
    assert early[0].units == 20.0
    assert _plan(last_day_units=0.0, second_day_units=40.0, expected_unsold_second_day=5.0) == []


def test_a_day_early_markdown_uses_the_existing_promotion_step_not_the_deeper_cut() -> None:
    (early,) = _plan(last_day_units=0.0, second_day_units=40.0, expected_unsold_second_day=20.0)
    assert early.step_pct == RULES.promo_pct_in_data
    assert early.step_pct < RULES.step_1_pct
    assert early.price_after == pytest.approx(40 * (1 - RULES.promo_pct_in_data / 100))


def test_a_day_early_markdown_still_respects_the_cost_floor() -> None:
    assert (
        _plan(
            last_day_units=0.0,
            second_day_units=40.0,
            expected_unsold_second_day=20.0,
            price=40.0,
            unit_cost=36.0,  # 15% off is 34, below cost
        )
        == []
    )
