"""G07 and the engine: playbook limits for markdown, transfer and surplus, and fail-safe rules."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harabhara.contracts import Suggestion
from harabhara.decisions.surplus import Buyer
from harabhara.rules.engine import RulesEngine, Verdict
from harabhara.rules.guardrails import Facts, Violation
from harabhara.settings import load_config
from tests.rules.conftest import (
    IST,
    MORNING,
    good_facts,
    markdown,
    order,
    suggestion,
    surplus,
    transfer,
)

CFG = load_config()
ENGINE = RulesEngine(CFG)
STEP_2 = CFG.rules.markdown.step_2_pct


def _rules(verdict: Verdict) -> set[str]:
    return {v.rule for v in verdict.violations}


# ---- markdown ------------------------------------------------------------------------------
def test_a_standard_markdown_is_allowed() -> None:
    assert ENGINE.evaluate(suggestion(markdown()), good_facts()).allowed


def test_a_step_that_is_not_in_the_playbook_is_blocked() -> None:
    assert "PB07" in _rules(ENGINE.evaluate(suggestion(markdown(step_pct=40.0)), good_facts()))


def test_the_second_step_is_only_for_leafy_greens_and_bananas() -> None:
    late = markdown(step_pct=STEP_2, start="18:30")
    assert "PB08" in _rules(ENGINE.evaluate(suggestion(late), good_facts(category="Vegetables")))
    greens = suggestion(late, sku_id="P13")
    assert "PB08" not in _rules(ENGINE.evaluate(greens, good_facts(category="Leafy greens")))
    banana = suggestion(late, sku_id="P04")
    assert "PB08" not in _rules(ENGINE.evaluate(banana, good_facts(category="Fruits")))


def test_the_second_step_cannot_start_before_the_evening_hour() -> None:
    early = suggestion(markdown(step_pct=STEP_2, start="10:00"), sku_id="P13")
    assert "PB08" in _rules(ENGINE.evaluate(early, good_facts(category="Leafy greens")))


def test_before_the_evening_hour_a_markdown_may_not_go_below_cost() -> None:
    below = good_facts(price=40.0, unit_cost=35.0)  # 30% off = 28 < 35
    assert "PB09" in _rules(ENGINE.evaluate(suggestion(markdown(start="07:00")), below))
    assert "PB09" not in _rules(ENGINE.evaluate(suggestion(markdown(start="18:00")), below))


def test_an_unknown_price_or_cost_blocks_an_early_markdown() -> None:
    assert "PB09" in _rules(ENGINE.evaluate(suggestion(markdown()), good_facts(price=None)))


def test_a_markdown_of_a_large_share_of_the_delivery_needs_the_area_manager() -> None:
    big = suggestion(markdown(units=80.0), approver_role="store_manager")
    assert "PB10" in _rules(ENGINE.evaluate(big, good_facts(day_delivery_units=100.0)))
    ok = suggestion(markdown(units=80.0), approver_role="area_manager")
    assert "PB10" not in _rules(ENGINE.evaluate(ok, good_facts(day_delivery_units=100.0)))
    small = suggestion(markdown(units=10.0), approver_role="store_manager")
    assert "PB10" not in _rules(ENGINE.evaluate(small, good_facts(day_delivery_units=100.0)))


@given(
    pct=st.sampled_from([10.0, 30.0, 40.0, 50.0, 70.0]),
    hour=st.integers(0, 23),
    price=st.floats(5, 200),
    cost=st.floats(1, 150),
)
def test_no_allowed_markdown_ever_sells_below_cost_before_the_evening_hour(
    pct: float, hour: int, price: float, cost: float
) -> None:
    s = suggestion(markdown(step_pct=pct, start=f"{hour:02d}:00"), sku_id="P13")
    facts = good_facts(category="Leafy greens", price=price, unit_cost=cost)
    if ENGINE.evaluate(s, facts).allowed and hour < CFG.rules.markdown.step_2_after_hour:
        assert price * (1 - pct / 100) >= cost


# ---- transfer ------------------------------------------------------------------------------
def _transfer(**over: Any) -> Suggestion:
    return suggestion(transfer(**over), approver_role="area_manager")


def test_a_good_transfer_is_allowed() -> None:
    assert ENGINE.evaluate(_transfer(), good_facts()).allowed


def test_the_van_cost_must_match_the_playbook() -> None:
    assert "PB12" in _rules(ENGINE.evaluate(_transfer(van_cost_inr=100.0), good_facts()))


def test_a_van_that_arrives_after_the_cutoff_is_blocked() -> None:
    assert "PB11" in _rules(ENGINE.evaluate(_transfer(leave_by="10:30"), good_facts()))


def test_leafy_greens_do_not_move_after_the_cutoff_hour() -> None:
    late = good_facts(category="Leafy greens", now_hour=12.5)
    assert "PB13" in _rules(ENGINE.evaluate(_transfer(), late))


def test_only_the_area_manager_approves_a_transfer_before_the_approval_hour() -> None:
    assert "PB14" in _rules(
        ENGINE.evaluate(suggestion(transfer(), approver_role="store_manager"), good_facts())
    )
    late = suggestion(
        transfer(), approver_role="area_manager", deadline=datetime(2026, 11, 4, 9, 30, tzinfo=IST)
    )
    assert "PB14" in _rules(ENGINE.evaluate(late, good_facts()))


def test_a_transfer_to_the_same_store_is_blocked() -> None:
    assert "PB11" in _rules(ENGINE.evaluate(_transfer(to_store="S01"), good_facts()))


@given(hour=st.integers(0, 12), minute=st.sampled_from([0, 15, 30, 45]))
def test_no_allowed_transfer_arrives_after_the_cutoff(hour: int, minute: int) -> None:
    s = _transfer(leave_by=f"{hour:02d}:{minute:02d}")
    if ENGINE.evaluate(s, good_facts()).allowed:
        trip = CFG.modeling.decisions.transfer_trip_minutes
        assert hour * 60 + minute + trip <= CFG.rules.transfer.must_arrive_before_hour * 60


# ---- surplus -------------------------------------------------------------------------------
def _buyer(**over: Any) -> Buyer:
    base = {
        "buyer_id": "B1",
        "buyer_type": "Pickle and sauce maker",
        "nearest_store": "S01",
        "skus": frozenset({"P01"}),
        "grades": frozenset({"B", "C"}),
        "price_share": 0.35,
        "max_units": 100.0,
        "window_start": time(21, 0),
        "window_end": time(23, 0),
        "notice_hours": 2,
    }
    return Buyer(**{**base, **over})


def test_a_surplus_match_the_buyer_can_take_is_allowed() -> None:
    assert ENGINE.evaluate(suggestion(surplus()), good_facts(buyer=_buyer())).allowed


def test_a_surplus_match_with_an_unknown_buyer_is_blocked() -> None:
    assert "PB16" in _rules(ENGINE.evaluate(suggestion(surplus()), good_facts()))


@pytest.mark.parametrize(
    "buyer",
    [
        _buyer(skus=frozenset({"P02"})),
        _buyer(grades=frozenset({"A"})),
        _buyer(max_units=10.0),
        _buyer(nearest_store="S05"),
    ],
)
def test_a_surplus_match_the_buyer_cannot_take_is_blocked(buyer: Buyer) -> None:
    assert "PB16" in _rules(ENGINE.evaluate(suggestion(surplus()), good_facts(buyer=buyer)))


# ---- the engine itself ---------------------------------------------------------------------
def test_the_kill_switch_blocks_everything() -> None:
    for payload in (markdown(), order(), surplus()):
        verdict = ENGINE.evaluate(suggestion(payload), good_facts(kill_switch=True, buyer=_buyer()))
        assert "G12" in _rules(verdict)


def test_only_proposals_can_leave_the_system() -> None:
    assert "G01" in _rules(ENGINE.evaluate(suggestion(markdown(), state="approved"), good_facts()))


def test_thin_history_must_be_shown_as_a_driver() -> None:
    from harabhara.contracts import Driver

    assert "G10" in _rules(ENGINE.evaluate(suggestion(order()), good_facts(thin_history=True)))
    flagged = suggestion(
        order(), drivers=[Driver(kind="recent_sellout", direction="none", code="thin_history")]
    )
    assert "G10" not in _rules(ENGINE.evaluate(flagged, good_facts(thin_history=True)))


def test_filtering_keeps_the_allowed_and_reports_why_the_rest_were_blocked() -> None:
    good = suggestion(markdown(), id="good")
    bad = suggestion(markdown(step_pct=40.0), id="bad")
    allowed, blocked = ENGINE.filter_suggestions([(good, good_facts()), (bad, good_facts())])
    assert [s.id for s in allowed] == ["good"]
    assert [b.suggestion.id for b in blocked] == ["bad"]
    assert blocked[0].violations
    assert all(v.message for v in blocked[0].violations)


def test_an_engine_fault_blocks_instead_of_allowing(monkeypatch: pytest.MonkeyPatch) -> None:
    from harabhara.rules import guardrails

    def boom(*_: object) -> list[Violation]:
        msg = "check failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(guardrails, "check_markdown", boom)
    verdict = ENGINE.evaluate(suggestion(markdown()), good_facts())
    assert not verdict.allowed
    assert "G12" in _rules(verdict)


def test_the_good_fixtures_really_are_good() -> None:
    """Guard against tests that pass only because every fixture is already blocked."""
    assert MORNING.hour == 8
    assert isinstance(good_facts(), Facts)
    for payload in (markdown(), order()):
        assert ENGINE.evaluate(suggestion(payload), good_facts()).allowed
