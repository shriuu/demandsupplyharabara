"""G08: a recall or safety flag removes the lot from everything immediately."""

from __future__ import annotations

from harabhara.rules.engine import RulesEngine
from harabhara.rules.guardrails import Facts
from tests.rules.conftest import good_facts, markdown, order, suggestion, surplus, transfer


def _blocked_by_recall(engine: RulesEngine, s, facts: Facts) -> bool:  # type: ignore[no-untyped-def]
    return any(v.rule == "G08" for v in engine.evaluate(s, facts).violations)


def test_every_kind_of_suggestion_is_blocked_for_a_recalled_lot(engine: RulesEngine) -> None:
    facts = good_facts(recalled=frozenset({("S01", "P01")}))
    for payload in (markdown(), transfer(), surplus(), order()):
        s = suggestion(payload, approver_role="area_manager")
        assert _blocked_by_recall(engine, s, facts), type(payload).__name__


def test_a_recall_on_one_store_does_not_block_another(engine: RulesEngine) -> None:
    facts = good_facts(recalled=frozenset({("S05", "P01")}))
    assert not _blocked_by_recall(engine, suggestion(markdown()), facts)


def test_a_recall_on_one_product_does_not_block_another(engine: RulesEngine) -> None:
    facts = good_facts(recalled=frozenset({("S01", "P02")}))
    assert not _blocked_by_recall(engine, suggestion(markdown()), facts)
