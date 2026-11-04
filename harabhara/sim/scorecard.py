"""Waste, empty shelves and farmer share travel together (guardrail 4).

Every result the tool reports goes through ``together``: it refuses a waste figure without the
empty-shelf figure beside it, and a farmer share that is missing must say why.
"""

from __future__ import annotations

import math
from datetime import date

from harabhara.contracts import Scorecard


def together(
    *,
    scope: str,
    period_start: date,
    period_end: date,
    waste_pct: float | None,
    stockout_pct: float | None,
    farmer_share: float | None,
    farmer_share_definition: str | None,
) -> Scorecard:
    """The three measures as one object, or an error naming what is missing."""
    for name, value in (("waste", waste_pct), ("empty shelves", stockout_pct)):
        if value is None or math.isnan(value):
            msg = f"{name} is missing, so the result cannot be reported (guardrail 4)"
            raise ValueError(msg)
    assert waste_pct is not None
    assert stockout_pct is not None
    return Scorecard(
        scope=scope,
        period_start=period_start,
        period_end=period_end,
        waste_pct=waste_pct,
        stockout_pct=stockout_pct,
        farmer_share=farmer_share,
        farmer_share_definition=farmer_share_definition,
    )


def line(card: Scorecard) -> str:
    """One plain line with all three measures, for logs and reports."""
    farmer = "not known" if card.farmer_share is None else f"{card.farmer_share:.1%}"
    return (
        f"{card.scope}: waste {card.waste_pct:.1f}%, empty shelves {card.stockout_pct:.1f}%, "
        f"farmer share {farmer}"
    )
