"""Store-to-store transfers (playbook s6, brief T07).

A transfer moves stock a store will not sell to a nearby store that is likely to run out. It is
worth doing only if the sales it saves beat the van trip. Rules: the van must reach the
receiving store before the cut-off; leafy greens do not move after the cut-off hour; only
pairs known to be within reach are used (the pack has no coordinates, so the pairs are those
already seen in logged transfers, owner question 15). Quantity is what the donor will not sell
and the receiver will miss. Every transfer needs the area manager's approval before 9 am.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass

from harabhara.settings.schema import Transfer


@dataclass(frozen=True)
class TransferProposal:
    from_store: str
    to_store: str
    units: float
    leave_by: str
    van_cost_inr: float
    net_benefit_inr: float


def leave_by(rules: Transfer, trip_minutes: int) -> str:
    """Latest departure that still arrives before the cut-off hour."""
    total = rules.must_arrive_before_hour * 60 - trip_minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def plan_transfers(
    *,
    category: str,
    now_hour: float,
    surplus: Mapping[str, float],
    shortage: Mapping[str, float],
    pairs: Set[tuple[str, str]],
    price: Mapping[str, float],
    markdown_share: float,
    rules: Transfer,
    trip_minutes: int,
) -> list[TransferProposal]:
    """Transfers for one product on a morning, best first. ``markdown_share`` is the share of the
    price the donor would still recover by marking the units down instead."""
    if category == "Leafy greens" and now_hour >= rules.leafy_greens_no_transfer_after_hour:
        return []
    latest = rules.must_arrive_before_hour * 60 - trip_minutes
    if now_hour * 60 > latest:
        return []
    depart = leave_by(rules, trip_minutes)

    left_to_give = dict(surplus)
    left_to_get = dict(shortage)
    candidates = []
    for donor, give in surplus.items():
        for receiver, get in shortage.items():
            if donor == receiver or (donor, receiver) not in pairs:
                continue
            units = min(give, get)
            gain = units * (price.get(receiver, 0.0) - price.get(donor, 0.0) * markdown_share)
            candidates.append((gain - rules.van_cost_inr, donor, receiver))
    proposals = []
    for _, donor, receiver in sorted(candidates, reverse=True):
        units = min(left_to_give[donor], left_to_get[receiver])
        if units <= 0:
            continue
        net = (
            units * (price.get(receiver, 0.0) - price.get(donor, 0.0) * markdown_share)
            - rules.van_cost_inr
        )
        if net <= 0:
            continue
        left_to_give[donor] -= units
        left_to_get[receiver] -= units
        proposals.append(TransferProposal(donor, receiver, units, depart, rules.van_cost_inr, net))
    return proposals
