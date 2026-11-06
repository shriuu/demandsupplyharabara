"""Markdown suggestions within the playbook's steps (playbook s5, brief stretch goal).

Standard: on a product's last sellable day, 30% off from opening; a second step of 50% from the
second-step hour for leafy greens and bananas only. The floor is the purchase cost: before the
second-step hour a markdown that would sell below cost waits until that hour.

Optimised timing: when a large share of a lot is expected to expire unsold, suggest the existing
promotion step (the data's 15% promotion, the smallest cut) a day early; the playbook's 30% stays
for the last day. The owner allowed a day-early start (question 8), so it is flagged
``earlier_than_last_day`` and needs approval. The response to a markdown is an assumption (the
lowest lift measured in the 15% promotion rows), never extrapolated to deeper cuts.
"""

from __future__ import annotations

from dataclasses import dataclass

from harabhara.settings.schema import Markdown


@dataclass(frozen=True)
class MarkdownProposal:
    step_pct: float
    start: str
    units: float
    price_after: float
    expected_recovery_inr: float
    earlier_than_last_day: bool
    note: str  # why this start time, in plain words


def _recovery(
    expected_unsold: float, baseline_demand: float, lift: float, price_after: float
) -> float:
    """Units that would be binned but sell at the markdown price, times that price."""
    extra = baseline_demand * lift
    return min(expected_unsold, extra) * price_after


def plan_markdown(
    *,
    sku_id: str,
    category: str,
    price: float,
    unit_cost: float,
    last_day_units: float,
    expected_unsold_last_day: float,
    second_day_units: float,
    expected_unsold_second_day: float,
    baseline_demand: float,
    opening: str,
    rules: Markdown,
    lift: float,
    earlier_min_share: float,
) -> list[MarkdownProposal]:
    """Markdown suggestions for one store and product on a morning."""
    step_hour = f"{rules.step_2_after_hour:02d}:00"
    second_step_hour = f"{rules.step_2_start_hour:02d}:00"
    proposals: list[MarkdownProposal] = []

    if last_day_units > 0:
        price_1 = price * (1 - rules.step_1_pct / 100)
        below_cost = price_1 < unit_cost
        start_1 = step_hour if below_cost else opening
        proposals.append(
            MarkdownProposal(
                step_pct=rules.step_1_pct,
                start=start_1,
                units=last_day_units,
                price_after=price_1,
                expected_recovery_inr=_recovery(
                    expected_unsold_last_day, baseline_demand, lift, price_1
                ),
                earlier_than_last_day=False,
                note=(
                    "last sellable day; below cost until the second-step hour, so it starts then"
                    if below_cost
                    else "last sellable day, from opening"
                ),
            )
        )
        if category in rules.step_2_categories_or_skus or sku_id in rules.step_2_categories_or_skus:
            price_2 = price * (1 - rules.step_2_pct / 100)
            proposals.append(
                MarkdownProposal(
                    step_pct=rules.step_2_pct,
                    start=second_step_hour,
                    units=last_day_units,
                    price_after=price_2,
                    expected_recovery_inr=_recovery(
                        expected_unsold_last_day * 0.5, baseline_demand, lift, price_2
                    ),
                    earlier_than_last_day=False,
                    note="second step for leafy greens and bananas after the evening hour",
                )
            )

    if (
        rules.earlier_start_allowed
        and second_day_units > 0
        and expected_unsold_second_day >= earlier_min_share * second_day_units
    ):
        price_early = price * (1 - rules.promo_pct_in_data / 100)
        if price_early >= unit_cost:  # the floor applies to an early markdown too
            proposals.append(
                MarkdownProposal(
                    step_pct=rules.promo_pct_in_data,
                    start=opening,
                    units=min(expected_unsold_second_day, second_day_units),
                    price_after=price_early,
                    expected_recovery_inr=_recovery(
                        expected_unsold_second_day, baseline_demand, lift, price_early
                    ),
                    earlier_than_last_day=True,
                    note="much of this stock is expected to expire unsold, so start a day early",
                )
            )
    return proposals
