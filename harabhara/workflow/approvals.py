"""The approval state machine (guardrail 1).

A person approves, edits (with a reason) or rejects a proposed suggestion. A deadline that
passes expires it. These functions only compute the next state; nothing here, or anywhere in
the service, orders, reprices or moves stock. ``approved`` and ``edited`` are records of a
person's decision for the store to act on in its usual way.
"""

from __future__ import annotations

from datetime import datetime

from harabhara.contracts import Approval, Role, Suggestion, SuggestionState
from harabhara.settings import AppConfig
from harabhara.workflow.deadlines import is_overdue

ACTION_TO_STATE: dict[str, SuggestionState] = {
    "approve": "approved",
    "edit": "edited",
    "reject": "rejected",
}

# Only a proposed suggestion can move. Every other state is final for the person's decision;
# ``done`` is reserved for the outcome record after the day closes.
TRANSITIONS: dict[SuggestionState, frozenset[SuggestionState]] = {
    "proposed": frozenset({"approved", "edited", "rejected", "expired"}),
    "approved": frozenset({"done"}),
    "edited": frozenset({"done"}),
    "rejected": frozenset(),
    "expired": frozenset(),
    "done": frozenset(),
}


class DecisionError(Exception):
    """A decision that the rules do not allow. ``code`` maps to an HTTP status in the API."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def assert_manual_only(cfg: AppConfig) -> None:
    """Refuse to run if the config would let the system act without a person (guardrail 1)."""
    if cfg.rules.automation.auto_order_allowed or not cfg.rules.ordering.approval_required:
        msg = "config allows acting without approval; this service only supports approval"
        raise RuntimeError(msg)


def may_decide(suggestion: Suggestion, role: Role, store_id: str | None) -> bool:
    """Only the suggestion's approver role decides; a store manager only for their own store."""
    if role != suggestion.approver_role:
        return False
    return not (role == "store_manager" and store_id != suggestion.store_id)


def next_state(suggestion: Suggestion, approval: Approval, now: datetime) -> SuggestionState:
    """Validate a decision and return the state it leads to."""
    if suggestion.state != "proposed":
        raise DecisionError("not_proposed", f"suggestion is already {suggestion.state}")
    if is_overdue(suggestion.deadline, now):
        raise DecisionError("overdue", "the deadline has passed; the suggestion expires")
    if approval.suggestion_id != suggestion.id:
        raise DecisionError("mismatch", "decision is for a different suggestion")
    target = ACTION_TO_STATE[approval.action]
    if target not in TRANSITIONS[suggestion.state]:  # pragma: no cover - table guards this
        raise DecisionError("illegal", f"cannot move from {suggestion.state} to {target}")
    return target


def due_for_expiry(suggestion: Suggestion, now: datetime) -> bool:
    return suggestion.state == "proposed" and is_overdue(suggestion.deadline, now)
