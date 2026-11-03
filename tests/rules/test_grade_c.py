"""G05 / PB02: grade C never goes on a shelf, a markdown crate or a store-to-store move."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harabhara.rules.engine import RulesEngine
from tests.rules.conftest import good_facts, markdown, suggestion, surplus, transfer


def test_grade_c_markdown_is_blocked(engine: RulesEngine) -> None:
    verdict = engine.evaluate(suggestion(markdown()), good_facts(lot_grade="C"))
    assert any(v.rule == "G05" for v in verdict.violations)


def test_grade_c_transfer_is_blocked(engine: RulesEngine) -> None:
    s = suggestion(transfer(), approver_role="area_manager")
    assert any(v.rule == "G05" for v in engine.evaluate(s, good_facts(lot_grade="C")).violations)


def test_grade_c_surplus_to_a_buyer_who_takes_it_is_not_a_grade_rule_violation(
    engine: RulesEngine,
) -> None:
    s = suggestion(surplus(grade="C"))
    verdict = engine.evaluate(s, good_facts(lot_grade="C"))
    assert not any(v.rule == "G05" for v in verdict.violations)


@pytest.mark.parametrize("grade", ["A", "B"])
def test_grades_a_and_b_are_not_blocked_by_this_rule(engine: RulesEngine, grade: str) -> None:
    verdict = engine.evaluate(suggestion(markdown()), good_facts(lot_grade=grade))
    assert not any(v.rule == "G05" for v in verdict.violations)


@given(units=st.floats(1, 500), pct=st.sampled_from([30.0, 50.0]), hour=st.integers(0, 23))
def test_no_markdown_of_grade_c_is_ever_allowed(units: float, pct: float, hour: int) -> None:
    from harabhara.settings import load_config

    s = suggestion(markdown(units=units, step_pct=pct, start=f"{hour:02d}:00"))
    assert not RulesEngine(load_config()).evaluate(s, good_facts(lot_grade="C")).allowed
