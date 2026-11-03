"""Playbook s7: notice period, pickup window, grade, product and capacity."""

from __future__ import annotations

from datetime import UTC, datetime, time

from harabhara.decisions.surplus import Buyer, SurplusPlan, earliest_pickup, plan_surplus

NOW = datetime(2026, 11, 3, 13, 0, tzinfo=UTC)


def _buyer(**over: object) -> Buyer:
    base: dict[str, object] = {
        "buyer_id": "B1",
        "buyer_type": "Pickle and sauce maker",
        "nearest_store": "S02",
        "skus": frozenset({"P01"}),
        "grades": frozenset({"B", "C"}),
        "price_share": 0.35,
        "max_units": 100.0,
        "window_start": time(14, 0),
        "window_end": time(16, 0),
        "notice_hours": 2,
    }
    return Buyer(**{**base, **over})  # type: ignore[arg-type]


def _plan(
    buyers: list[Buyer], units: float = 60.0, grade: str = "B", used: dict[str, float] | None = None
) -> SurplusPlan:
    return plan_surplus(
        store_id="S02",
        sku_id="P01",
        grade=grade,
        units=units,
        retail_price=40.0,
        now=NOW,
        buyers=buyers,
        used_capacity=used or {},
        horizon_hours=36,
    )


def test_pickup_is_after_the_notice_period() -> None:
    pickup = earliest_pickup(_buyer(window_start=time(14, 0), notice_hours=2), NOW, 36)
    assert pickup is not None
    assert pickup >= NOW.replace(hour=15)  # 13:00 + 2h notice = 15:00, so the next day's 14:00
    quick = earliest_pickup(_buyer(window_start=time(15, 0), notice_hours=2), NOW, 36)
    assert quick == NOW.replace(hour=15)


def test_a_buyer_that_cannot_collect_within_the_horizon_is_skipped() -> None:
    far = _buyer(notice_hours=12, window_start=time(6, 0))
    assert earliest_pickup(far, NOW, 4) is None


def test_the_product_the_grade_and_the_store_must_all_fit() -> None:
    assert _plan([_buyer(skus=frozenset({"P02"}))]).matches == []
    assert _plan([_buyer(grades=frozenset({"A"}))]).matches == []
    assert _plan([_buyer(nearest_store="S05")]).matches == []
    assert len(_plan([_buyer()]).matches) == 1


def test_grade_c_goes_only_to_buyers_who_take_grade_c() -> None:
    assert _plan([_buyer(grades=frozenset({"A", "B"}))], grade="C").matches == []
    assert len(_plan([_buyer(grades=frozenset({"B", "C"}))], grade="C").matches) == 1


def test_capacity_is_respected_across_stores_and_leftover_is_reported() -> None:
    plan = _plan([_buyer(max_units=40.0)], units=60.0, used={"B1": 10.0})
    assert plan.matches[0].units == 30.0
    assert plan.unplaced_units == 30.0


def test_recovery_is_units_times_the_share_of_the_retail_price() -> None:
    (match,) = _plan([_buyer()]).matches
    assert match.expected_recovery_inr == 60.0 * 0.35 * 40.0
