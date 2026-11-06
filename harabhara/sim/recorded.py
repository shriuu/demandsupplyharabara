"""Scorecards from what stores and the DC recorded, in the same shape as the data-pack ones.

Waste, empty shelves and farmer share travel together (guardrail 4). Units received are not
recorded, so waste here is thrown away over sold plus thrown away: it will differ from the
data-pack figure (binned over received) and is labelled as such.
"""

from __future__ import annotations

from datetime import date, timedelta

from harabhara.contracts import OutcomeRecord, Scorecard
from harabhara.sim.scorecard import together

FARMER_DEFINITION = (
    "Share of purchased volume that came from farmer groups, from the purchases the DC lead "
    "recorded; a chain-wide figure, because purchases are not recorded per store."
)
NO_PURCHASES = "No purchases recorded in this period, so farmer share is not known."
NOT_PER_STORE = "Purchases are recorded for the whole chain, not per store."


def scorecards_from_outcomes(
    records: list[OutcomeRecord], today: date, days: int
) -> list[Scorecard]:
    """Chain and per-store scorecards over the last ``days`` days; empty if nothing was closed."""
    start = today - timedelta(days=days - 1)
    inside = [r for r in records if start <= r.on <= today]
    closings = [r for r in inside if r.kind == "closing"]
    bought = {"farmer_group": 0.0, "spot": 0.0}
    for r in inside:
        if r.kind == "purchase" and r.source and r.units_bought is not None:
            bought[r.source] += r.units_bought
    total_bought = sum(bought.values())

    def card(scope: str, rows: list[OutcomeRecord]) -> Scorecard | None:
        sold = sum(r.units_sold or 0.0 for r in rows)
        wasted = sum(r.units_wasted or 0.0 for r in rows)
        if not rows or sold + wasted <= 0:
            return None
        if scope != "chain":
            share, why = None, NOT_PER_STORE
        elif total_bought > 0:
            share, why = bought["farmer_group"] / total_bought, FARMER_DEFINITION
        else:
            share, why = None, NO_PURCHASES
        return together(
            scope=scope,
            period_start=start,
            period_end=today,
            waste_pct=100 * wasted / (sold + wasted),
            stockout_pct=100 * sum(1 for r in rows if r.sold_out) / len(rows),
            farmer_share=share,
            farmer_share_definition=why,
        )

    cards = [card("chain", closings)]
    for store in sorted({r.store_id for r in closings if r.store_id}):
        cards.append(card(store, [r for r in closings if r.store_id == store]))
    return [c for c in cards if c is not None]
