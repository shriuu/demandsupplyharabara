"""Playbook s6: van cost, small transfers, leafy greens cut-off, arrival before the cut-off."""

from __future__ import annotations

import pytest

from harabhara.decisions.transfer import leave_by, plan_transfers
from harabhara.settings import load_config

RULES = load_config().rules.transfer
PAIRS = {("S01", "S02"), ("S02", "S01")}
PRICE = {"S01": 80.0, "S02": 80.0}


def _plan(**over: object):  # type: ignore[no-untyped-def]
    base: dict[str, object] = {
        "category": "Vegetables",
        "now_hour": 7.5,
        "surplus": {"S01": 30.0},
        "shortage": {"S02": 25.0},
        "pairs": PAIRS,
        "price": PRICE,
        "markdown_share": 0.7,
        "rules": RULES,
        "trip_minutes": 60,
    }
    return plan_transfers(**{**base, **over})  # type: ignore[arg-type]


def test_a_transfer_moves_what_the_receiver_will_miss_and_carries_the_van_cost() -> None:
    (t,) = _plan()
    assert (t.from_store, t.to_store, t.units) == ("S01", "S02", 25.0)
    assert t.van_cost_inr == RULES.van_cost_inr
    assert t.net_benefit_inr > 0


def test_the_van_leaves_early_enough_to_arrive_before_the_cutoff() -> None:
    hours, minutes = leave_by(RULES, 60).split(":")
    assert int(hours) * 60 + int(minutes) + 60 <= RULES.must_arrive_before_hour * 60


def test_too_late_for_the_van_means_no_transfer() -> None:
    assert _plan(now_hour=float(RULES.must_arrive_before_hour)) == []


def test_a_transfer_that_does_not_beat_the_van_cost_is_not_suggested() -> None:
    cheap = {"S01": 2.0, "S02": 2.0}  # a few cheap units never pay for a van
    assert _plan(surplus={"S01": 5.0}, shortage={"S02": 5.0}, price=cheap) == []


def test_leafy_greens_do_not_move_after_the_cutoff_hour() -> None:
    assert (
        _plan(category="Leafy greens", now_hour=float(RULES.leafy_greens_no_transfer_after_hour))
        == []
    )
    assert _plan(category="Leafy greens", now_hour=7.0)


def test_only_pairs_known_to_be_in_reach_are_used() -> None:
    assert _plan(pairs={("S03", "S04")}) == []


def test_one_van_trip_per_pair_and_no_unit_is_moved_twice() -> None:
    plans = _plan(
        surplus={"S01": 30.0, "S03": 30.0},
        shortage={"S02": 60.0},
        pairs={("S01", "S02"), ("S03", "S02")},
        price={"S01": 80.0, "S02": 80.0, "S03": 80.0},
    )
    assert sum(p.units for p in plans) == pytest.approx(60.0)
    assert sum(p.units for p in plans if p.from_store == "S01") <= 30.0


def test_the_last_few_units_are_left_alone_when_a_second_van_would_not_pay() -> None:
    plans = _plan(
        surplus={"S01": 30.0, "S03": 30.0},
        shortage={"S02": 40.0},
        pairs={("S01", "S02"), ("S03", "S02")},
        price={"S01": 80.0, "S02": 80.0, "S03": 80.0},
    )
    assert sum(p.units for p in plans) == pytest.approx(
        30.0
    )  # 10 units never pay for a second trip
