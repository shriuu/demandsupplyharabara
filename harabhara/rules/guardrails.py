"""The guardrails, one check per rule (CLAUDE.md s5, playbook limits).

Each check takes a suggestion and the facts it depends on and returns the rules it breaks. A
check that cannot be verified because a fact is missing fails safe: the suggestion is blocked,
never waved through. Limits come from ``config/``; nothing is hard-coded here.
"""

from __future__ import annotations

from dataclasses import dataclass

from harabhara.contracts import (
    MarkdownPayload,
    Scorecard,
    Suggestion,
    SurplusPayload,
    TransferPayload,
)
from harabhara.decisions.surplus import Buyer
from harabhara.settings.schema import AppConfig


@dataclass(frozen=True)
class Violation:
    rule: str  # e.g. "G06" or "PB09"
    message: str


@dataclass(frozen=True)
class Facts:
    """What the checks need to know beyond the suggestion itself."""

    kill_switch: bool = False
    recalled: frozenset[tuple[str, str]] = frozenset()  # (store, product) with a recall flag
    category: str = ""
    lot_grade: str | None = None
    life_left_days: int | None = None  # sellable days left for the lot, including today
    price: float | None = None
    unit_cost: float | None = None
    thin_history: bool = False
    day_delivery_units: float | None = None
    now_hour: float | None = None
    buyer: Buyer | None = None


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def check_kill_switch(facts: Facts) -> list[Violation]:
    if facts.kill_switch:
        return [Violation("G12", "the kill switch is on: no suggestions are shown")]
    return []


def check_person_decides(s: Suggestion, cfg: AppConfig) -> list[Violation]:
    """G01: the system only proposes; a person approves, edits or rejects."""
    found = []
    if s.state != "proposed":
        found.append(Violation("G01", f"a new suggestion must start as proposed, not {s.state}"))
    if not cfg.rules.ordering.approval_required or cfg.rules.automation.auto_order_allowed:
        found.append(Violation("G01", "configuration allows acting without approval"))
    return found


def check_reason(s: Suggestion, cfg: AppConfig) -> list[Violation]:
    """G09: one sentence a manager would say, built from real drivers."""
    reason = s.reason.strip()
    found = []
    if not reason:
        found.append(Violation("G09", "no reason, no suggestion"))
    if "\n" in reason:
        found.append(Violation("G09", "the reason must be one sentence on one line"))
    if len(reason) > cfg.rules.explanations.max_reason_chars:
        found.append(Violation("G09", "the reason is too long to be one sentence"))
    if not s.drivers:
        found.append(Violation("G09", "the reason must come from at least one real driver"))
    return found


def check_thin_history(s: Suggestion, facts: Facts) -> list[Violation]:
    """G10: a suggestion built on thin history must say so."""
    if facts.thin_history and not any(d.code == "thin_history" for d in s.drivers):
        return [Violation("G10", "thin history must be shown as a driver of the suggestion")]
    return []


def check_recall(s: Suggestion, facts: Facts) -> list[Violation]:
    """G08: a recall or safety flag removes the lot from everything immediately."""
    if (s.store_id, s.sku_id) in facts.recalled:
        return [Violation("G08", "this lot has a recall or safety flag")]
    return []


def check_grade_c(s: Suggestion, facts: Facts) -> list[Violation]:
    """G05 / PB02: grade C never goes on a shelf, a markdown crate or a store-to-store move."""
    if facts.lot_grade == "C" and isinstance(s.payload, MarkdownPayload | TransferPayload):
        return [Violation("G05", "grade C produce is for B2B buyers or processing, not display")]
    return []


def check_last_sellable_day(s: Suggestion, facts: Facts) -> list[Violation]:
    """G06 / PB06: never suggest selling past the last sellable day."""
    payload = s.payload
    if not isinstance(payload, MarkdownPayload | TransferPayload):
        return []
    if facts.life_left_days is None:
        return [Violation("G06", "remaining shelf life is unknown, so the sale cannot be verified")]
    if facts.life_left_days < 1:
        return [Violation("G06", "this stock is past its last sellable day")]
    if (
        isinstance(payload, MarkdownPayload)
        and payload.earlier_than_last_day
        and facts.life_left_days < 2
    ):
        return [Violation("G06", "an early markdown needs at least two sellable days left")]
    return []


def check_markdown(s: Suggestion, facts: Facts, cfg: AppConfig) -> list[Violation]:
    """G07 / PB07 to PB10: steps, second-step products, purchase-cost floor, approval."""
    payload = s.payload
    if not isinstance(payload, MarkdownPayload):
        return []
    rules = cfg.rules.markdown
    found: list[Violation] = []
    second_hour = rules.step_2_after_hour * 60
    allowed_steps = {rules.step_1_pct, rules.step_2_pct}
    if payload.earlier_than_last_day:
        if not rules.earlier_start_allowed:
            found.append(Violation("PB07", "a day-early markdown is not allowed by the owner"))
        allowed_steps = {rules.promo_pct_in_data}  # a day early uses only the existing promotion
    if payload.step_pct not in allowed_steps:
        found.append(Violation("PB07", f"{payload.step_pct}% is not one of the playbook steps"))
    starts = _minutes(payload.start)
    if payload.step_pct == rules.step_2_pct:
        if (
            facts.category not in rules.step_2_categories_or_skus
            and s.sku_id not in rules.step_2_categories_or_skus
        ):
            found.append(Violation("PB08", "the second step is only for leafy greens and bananas"))
        if starts < second_hour:
            found.append(Violation("PB08", "the second step cannot start before the evening hour"))
    if starts < second_hour:
        if facts.price is None or facts.unit_cost is None:
            found.append(
                Violation("PB09", "price or cost is unknown, so the floor cannot be verified")
            )
        elif facts.price * (1 - payload.step_pct / 100) < facts.unit_cost:
            found.append(
                Violation("PB09", "before the evening hour a markdown may not go below cost")
            )
    if facts.day_delivery_units is not None and facts.day_delivery_units > 0:
        share = rules.area_manager_approval_if_share_of_days_delivery_above
        if payload.units / facts.day_delivery_units > share and s.approver_role != "area_manager":
            found.append(
                Violation("PB10", "a markdown this large needs the area manager's approval")
            )
    return found


def check_transfer(s: Suggestion, facts: Facts, cfg: AppConfig) -> list[Violation]:
    """G07 / PB11 to PB14: van cost, arrival before the cut-off, greens cut-off, approver."""
    payload = s.payload
    if not isinstance(payload, TransferPayload):
        return []
    rules = cfg.rules.transfer
    trip = cfg.modeling.decisions.transfer_trip_minutes
    found: list[Violation] = []
    if payload.van_cost_inr != rules.van_cost_inr:
        found.append(Violation("PB12", "the van cost does not match the playbook"))
    if _minutes(payload.leave_by) + trip > rules.must_arrive_before_hour * 60:
        found.append(Violation("PB11", "the van would arrive after the morning cut-off"))
    if (
        facts.category == "Leafy greens"
        and (facts.now_hour or 0) >= rules.leafy_greens_no_transfer_after_hour
    ):
        found.append(Violation("PB13", "leafy greens are not transferred after the cut-off hour"))
    if s.approver_role != rules.approver:
        found.append(Violation("PB14", "transfers are approved by the area manager"))
    if s.deadline.hour * 60 + s.deadline.minute > rules.approve_by_hour * 60:
        found.append(Violation("PB14", "the approval deadline is after the approval hour"))
    if payload.from_store == payload.to_store:
        found.append(Violation("PB11", "a transfer needs two different stores"))
    return found


def check_surplus(s: Suggestion, facts: Facts) -> list[Violation]:
    """G07 / PB16: the buyer must take this product and grade, with capacity."""
    payload = s.payload
    if not isinstance(payload, SurplusPayload):
        return []
    buyer = facts.buyer
    if buyer is None:
        return [Violation("PB16", "the buyer is unknown, so the match cannot be verified")]
    found = []
    if s.sku_id not in buyer.skus:
        found.append(Violation("PB16", "this buyer does not take this product"))
    if payload.grade not in buyer.grades:
        found.append(Violation("PB16", "this buyer does not take this grade"))
    if payload.units > buyer.max_units:
        found.append(Violation("PB16", "this is more than the buyer can take in a day"))
    if buyer.nearest_store != s.store_id:
        found.append(Violation("PB16", "this buyer does not collect from this store"))
    return found


def check_spot_trim(trim_units: float, spot_units_available: float) -> list[Violation]:
    """G03: only spot (mandi) buying may be trimmed; confirmed farmer volume never is."""
    if trim_units > spot_units_available + 1e-9:
        return [Violation("G03", "trimming this much would cut into confirmed farmer volume")]
    return []


def check_purchase_price(price: float, floor: float) -> list[Violation]:
    """G02 / PB18: never recommend paying a farmer group below its contract floor."""
    if price < floor:
        return [Violation("G02", "this price is below the farmer group's contract floor")]
    return []


def check_scorecard(card: Scorecard) -> list[Violation]:
    """G04: waste, empty shelves and farmer share are shown together, never waste alone."""
    if card.farmer_share is None and not card.farmer_share_definition:
        return [Violation("G04", "farmer share is missing and no definition says why")]
    return []
