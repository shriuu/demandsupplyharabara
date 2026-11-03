"""Playbook s7: paying B2B first, then food banks, then animal feed or compost."""

from __future__ import annotations

from datetime import UTC, datetime, time

from harabhara.decisions.surplus import Buyer, plan_surplus

NOW = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


def _b(buyer_id: str, kind: str, share: float, cap: float = 50.0) -> Buyer:
    return Buyer(
        buyer_id=buyer_id,
        buyer_type=kind,
        nearest_store="S02",
        skus=frozenset({"P01"}),
        grades=frozenset({"B", "C"}),
        price_share=share,
        max_units=cap,
        window_start=time(21, 0),
        window_end=time(23, 0),
        notice_hours=2,
    )


def test_buyers_are_used_in_the_playbook_order() -> None:
    buyers = [
        _b("feed", "Animal feed / compost unit", 0.08),
        _b("bank", "Food bank (donation)", 0.0),
        _b("pickle", "Pickle and sauce maker", 0.35),
    ]
    plan = plan_surplus(
        store_id="S02", sku_id="P01", grade="B", units=120.0, retail_price=40.0,
        now=NOW, buyers=buyers, used_capacity={}, horizon_hours=36,
    )  # fmt: skip
    assert [m.buyer_id for m in plan.matches] == ["pickle", "bank", "feed"]
    assert plan.unplaced_units == 0


def test_among_paying_buyers_the_better_price_goes_first() -> None:
    buyers = [_b("low", "Pickle and sauce maker", 0.35), _b("high", "Juice bar", 0.45)]
    plan = plan_surplus(
        store_id="S02", sku_id="P01", grade="B", units=30.0, retail_price=40.0,
        now=NOW, buyers=buyers, used_capacity={}, horizon_hours=36,
    )  # fmt: skip
    assert plan.matches[0].buyer_id == "high"


def test_nothing_is_sent_to_landfill_unplaced_units_are_reported() -> None:
    plan = plan_surplus(
        store_id="S02", sku_id="P01", grade="B", units=80.0, retail_price=40.0,
        now=NOW, buyers=[_b("only", "Juice bar", 0.45, cap=50.0)],
        used_capacity={}, horizon_hours=36,
    )  # fmt: skip
    assert plan.unplaced_units == 30.0
