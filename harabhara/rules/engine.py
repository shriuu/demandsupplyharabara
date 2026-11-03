"""The rules engine: the filter between the recommender and anything a person sees.

``evaluate`` runs every check on one suggestion. ``filter_suggestions`` keeps the allowed ones
and returns the blocked ones with the rules they broke, so a block is never silent. If the
engine itself fails on a suggestion, that suggestion is blocked (fail safe, guardrail 12).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from harabhara.contracts import Suggestion
from harabhara.rules import guardrails as g
from harabhara.rules.guardrails import Facts, Violation
from harabhara.settings.schema import AppConfig


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    violations: list[Violation] = field(default_factory=list)


@dataclass(frozen=True)
class Blocked:
    suggestion: Suggestion
    violations: list[Violation]


class RulesEngine:
    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg

    def evaluate(self, s: Suggestion, facts: Facts) -> Verdict:
        cfg = self._cfg
        try:
            found = [
                *g.check_kill_switch(facts),
                *g.check_person_decides(s, cfg),
                *g.check_reason(s, cfg),
                *g.check_thin_history(s, facts),
                *g.check_recall(s, facts),
                *g.check_grade_c(s, facts),
                *g.check_last_sellable_day(s, facts),
                *g.check_markdown(s, facts, cfg),
                *g.check_transfer(s, facts, cfg),
                *g.check_surplus(s, facts),
            ]
        except Exception as error:
            found = [Violation("G12", f"the rules engine could not check this suggestion: {error}")]
        return Verdict(allowed=not found, violations=found)

    def filter_suggestions(
        self, items: Sequence[tuple[Suggestion, Facts]]
    ) -> tuple[list[Suggestion], list[Blocked]]:
        allowed: list[Suggestion] = []
        blocked: list[Blocked] = []
        for suggestion, facts in items:
            verdict = self.evaluate(suggestion, facts)
            if verdict.allowed:
                allowed.append(suggestion)
            else:
                blocked.append(Blocked(suggestion, verdict.violations))
        return allowed, blocked
