"""G09: every suggestion has a one-sentence reason from real drivers. No reason, no suggestion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harabhara.rules.engine import RulesEngine
from tests.rules.conftest import good_facts, markdown, suggestion


def test_a_good_reason_passes(engine: RulesEngine) -> None:
    assert engine.evaluate(suggestion(markdown()), good_facts()).allowed


def test_a_blank_reason_cannot_even_be_built() -> None:
    with pytest.raises(ValidationError):
        suggestion(markdown(), reason="")


def test_a_whitespace_reason_is_blocked(engine: RulesEngine) -> None:
    verdict = engine.evaluate(suggestion(markdown(), reason="   "), good_facts())
    assert not verdict.allowed
    assert any(v.rule == "G09" for v in verdict.violations)


def test_a_reason_over_one_line_is_blocked(engine: RulesEngine) -> None:
    verdict = engine.evaluate(
        suggestion(markdown(), reason="One thing.\nAnd another."), good_facts()
    )
    assert any(v.rule == "G09" for v in verdict.violations)


def test_a_rambling_reason_is_blocked(engine: RulesEngine, cfg) -> None:  # type: ignore[no-untyped-def]
    long = "word " * (cfg.rules.explanations.max_reason_chars // 4)
    verdict = engine.evaluate(suggestion(markdown(), reason=long), good_facts())
    assert any(v.rule == "G09" for v in verdict.violations)


def test_a_suggestion_with_no_driver_cannot_be_built() -> None:
    with pytest.raises(ValidationError):
        suggestion(markdown(), drivers=[])
