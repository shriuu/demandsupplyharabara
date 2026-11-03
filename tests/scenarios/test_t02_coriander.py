"""Brief T02: coriander at a walk-in store on a normal Tuesday.

Expected: an order close to expected demand, with a smaller buffer than today's, citing the
two-day shelf life.

The inputs are the averages measured on the training period for coriander at walk-in stores
before a Tuesday: demand 105 bunches, the managers' order 137, stock on hand 51. The demand
range is a typical calibrated one (about plus or minus 20%); the real forecast is checked in the
holdout run.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from harabhara.contracts import Range
from harabhara.decisions.builder import OrderInputs, Provenance, Series, build_order
from harabhara.reasons.writer import Names
from harabhara.rules.engine import RulesEngine
from harabhara.settings import load_config

CFG = load_config()
IST = ZoneInfo("Asia/Kolkata")

EXPECTED_DEMAND = 105.0
MANAGERS_ORDER = 137.0
STOCK_ON_HAND = 51.0


def test_t02_coriander_normal_tuesday() -> None:
    inputs = OrderInputs(
        series=Series(
            store_id="S01", sku_id="P13", category="Leafy greens", product="coriander",
            unit="bunch", format="Store", price=13.0, unit_cost=6.5, life_days=2,
            festival_sensitive=False,
        ),
        on=date(2026, 11, 3),  # a Tuesday
        demand=Range(low=85, likely=EXPECTED_DEMAND, high=128),
        stock=STOCK_ON_HAND,
        manager_units=MANAGERS_ORDER,
        thin_history=False,
        weekend=False,
        heavy_rain=False,
        festival_eve_intensity=0.0,
        hot_day=False,
        sold_out_at_origin=False,
        last_day_stock=0.0,
    )  # fmt: skip
    names = Names(product="coriander", unit="bunch", stores={"S01": "Jayanagar"}, buyers={})
    prov = Provenance("m", "d", CFG.digest)
    built = build_order(
        inputs, cfg=CFG, names=names, prov=prov, now=datetime(2026, 11, 2, 20, 30, tzinfo=IST)
    )
    assert built is not None
    suggestion, facts = built
    ours = suggestion.payload.recommended_units  # type: ignore[union-attr]

    # Close to expected demand: what will be on the shelf covers it without being wildly above.
    cover = ours + STOCK_ON_HAND
    assert cover >= EXPECTED_DEMAND
    assert cover <= EXPECTED_DEMAND * 1.35

    # A smaller buffer than today's: both the order and the total cover are below the managers'.
    assert ours < MANAGERS_ORDER
    assert cover < MANAGERS_ORDER + STOCK_ON_HAND
    assert (cover - EXPECTED_DEMAND) < (MANAGERS_ORDER + STOCK_ON_HAND - EXPECTED_DEMAND)

    # It cites the two-day shelf life, in one sentence, and the guardrails let it through.
    assert any(d.code == "two_day_life" for d in suggestion.drivers)
    assert "only lasts two days" in suggestion.reason
    assert RulesEngine(CFG).evaluate(suggestion, facts).allowed
