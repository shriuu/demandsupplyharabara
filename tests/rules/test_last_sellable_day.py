"""G06 / PB06: never suggest selling past the last sellable day."""

from __future__ import annotations

from harabhara.rules.engine import RulesEngine, Verdict
from tests.rules.conftest import good_facts, markdown, suggestion, transfer


def _rules(verdict: Verdict) -> set[str]:
    return {v.rule for v in verdict.violations}


def test_stock_with_a_day_left_can_be_marked_down(engine: RulesEngine) -> None:
    assert engine.evaluate(suggestion(markdown()), good_facts(life_left_days=1)).allowed


def test_stock_past_its_last_day_is_blocked(engine: RulesEngine) -> None:
    assert "G06" in _rules(engine.evaluate(suggestion(markdown()), good_facts(life_left_days=0)))
    s = suggestion(transfer(), approver_role="area_manager")
    assert "G06" in _rules(engine.evaluate(s, good_facts(life_left_days=0)))


def test_unknown_shelf_life_blocks_rather_than_guesses(engine: RulesEngine) -> None:
    assert "G06" in _rules(engine.evaluate(suggestion(markdown()), good_facts(life_left_days=None)))


def test_an_early_markdown_needs_two_days_left(engine: RulesEngine) -> None:
    early = suggestion(markdown(earlier_than_last_day=True))
    assert "G06" in _rules(engine.evaluate(early, good_facts(life_left_days=1)))
    assert "G06" not in _rules(engine.evaluate(early, good_facts(life_left_days=2)))
