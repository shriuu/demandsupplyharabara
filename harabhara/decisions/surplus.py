"""Match expected surplus to nearby buyers (playbook s7, brief T08).

Order of channels: paying B2B buyers, then food banks, then animal feed or compost. A buyer is
used only if it takes the product and grade, collects from this store, has capacity left, and
can collect after its notice period (the plan is made now, so earliest pickup is now + notice,
inside one of its pickup windows). Nothing edible goes to landfill: what cannot be placed is
reported as unplaced, not binned silently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pandas as pd

ANIMAL_FEED = "Animal feed / compost unit"
DASH = "\u2013"  # the pack writes pickup windows with an en dash
CHANNELS = ("b2b_paying", "food_bank_donation", "animal_feed_or_compost")


@dataclass(frozen=True)
class Buyer:
    buyer_id: str
    buyer_type: str
    nearest_store: str
    skus: frozenset[str]
    grades: frozenset[str]
    price_share: float
    max_units: float
    window_start: time
    window_end: time
    notice_hours: int

    @property
    def channel(self) -> str:
        if self.buyer_type == ANIMAL_FEED:
            return "animal_feed_or_compost"
        return "food_bank_donation" if self.price_share == 0 else "b2b_paying"


@dataclass(frozen=True)
class SurplusMatch:
    buyer_id: str
    channel: str
    units: float
    pickup_start: datetime
    window: str
    expected_recovery_inr: float
    price_share: float


@dataclass(frozen=True)
class SurplusPlan:
    matches: list[SurplusMatch]
    unplaced_units: float


def _parse_window(text: str) -> tuple[time, time]:
    start, end = text.replace("-", DASH).split(DASH)
    return time.fromisoformat(start.strip()), time.fromisoformat(end.strip())


def buyers_from_frame(frame: pd.DataFrame) -> list[Buyer]:
    buyers = []
    for row in frame.to_dict("records"):
        start, end = _parse_window(str(row["pickup_window"]))
        buyers.append(
            Buyer(
                buyer_id=str(row["buyer_id"]),
                buyer_type=str(row["buyer_type"]),
                nearest_store=str(row["nearest_store"]),
                skus=frozenset(s.strip() for s in str(row["skus_accepted"]).split(",")),
                grades=frozenset(g.strip() for g in str(row["grades_accepted"]).split(",")),
                price_share=float(row["price_as_share_of_retail"]),
                max_units=float(row["max_units_per_day"]),
                window_start=start,
                window_end=end,
                notice_hours=int(row["notice_needed_hours"]),
            )
        )
    return buyers


def earliest_pickup(buyer: Buyer, now: datetime, horizon_hours: int) -> datetime | None:
    """The first window start at or after now + notice, within the planning horizon."""
    ready = now + timedelta(hours=buyer.notice_hours)
    for offset in range(0, 3):
        start = datetime.combine(
            now.date() + timedelta(days=offset), buyer.window_start, tzinfo=now.tzinfo
        )
        if start >= ready:
            return start if start <= now + timedelta(hours=horizon_hours) else None
    return None


def plan_surplus(
    *,
    store_id: str,
    sku_id: str,
    grade: str,
    units: float,
    retail_price: float,
    now: datetime,
    buyers: Sequence[Buyer],
    used_capacity: Mapping[str, float],
    horizon_hours: int,
) -> SurplusPlan:
    """Greedy match in channel order, then by price paid, then by earliest pickup."""
    options = []
    for buyer in buyers:
        if buyer.nearest_store != store_id or sku_id not in buyer.skus or grade not in buyer.grades:
            continue
        pickup = earliest_pickup(buyer, now, horizon_hours)
        if pickup is None:
            continue
        options.append((CHANNELS.index(buyer.channel), -buyer.price_share, pickup, buyer))
    options.sort(key=lambda o: (o[0], o[1], o[2]))

    remaining = units
    matches: list[SurplusMatch] = []
    for _, _, pickup, buyer in options:
        room = buyer.max_units - used_capacity.get(buyer.buyer_id, 0.0)
        take = min(remaining, max(room, 0.0))
        if take <= 0:
            continue
        matches.append(
            SurplusMatch(
                buyer_id=buyer.buyer_id,
                channel=buyer.channel,
                units=take,
                pickup_start=pickup,
                window=f"{buyer.window_start:%H:%M}{DASH}{buyer.window_end:%H:%M}",
                expected_recovery_inr=take * buyer.price_share * retail_price,
                price_share=buyer.price_share,
            )
        )
        remaining -= take
        if remaining <= 1e-9:
            break
    return SurplusPlan(matches=matches, unplaced_units=max(remaining, 0.0))
