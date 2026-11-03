"""Price-shock check on public mandi prices (display only; the demand model never reads it)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PricePoint(BaseModel):
    """One modal price (Rs per kg) for one product on one day."""

    model_config = ConfigDict(frozen=True)

    on: date
    modal_inr: float


class PriceShock(BaseModel):
    model_config = ConfigDict(frozen=True)

    flag: Literal["up", "down", "none", "unknown"]
    ratio: float | None = None
    today_inr: float | None = None
    past_inr: float | None = None
    past_on: date | None = None


def price_shock(
    history: Sequence[PricePoint],
    today: date,
    *,
    lookback_days: int,
    ratio_threshold: float,
) -> PriceShock:
    """Compare today's modal price with the price ``lookback_days`` ago.

    ``unknown`` when either side is missing: a missing price is never guessed (guardrail 11).
    The past price is the latest one on or before the target day, and ``past_on`` says which
    day that was so the screen can be honest about it.
    """
    now = next((p for p in history if p.on == today), None)
    target = today - timedelta(days=lookback_days)
    earlier = [p for p in history if p.on <= target]
    if now is None or not earlier or now.modal_inr <= 0:
        return PriceShock(flag="unknown")
    past = max(earlier, key=lambda p: p.on)
    if past.modal_inr <= 0:
        return PriceShock(flag="unknown")
    ratio = now.modal_inr / past.modal_inr
    flag: Literal["up", "down", "none"] = "none"
    if ratio >= ratio_threshold:
        flag = "up"
    elif ratio <= 1 / ratio_threshold:
        flag = "down"
    return PriceShock(
        flag=flag, ratio=ratio, today_inr=now.modal_inr, past_inr=past.modal_inr, past_on=past.on
    )
