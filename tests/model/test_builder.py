"""Suggestion builder: real drivers, reasons, approvers, deadlines, and the guardrail engine."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from harabhara.contracts import MarkdownPayload, Range, Suggestion, TransferPayload
from harabhara.decisions.builder import (
    MorningStore,
    OrderInputs,
    Provenance,
    Series,
    build_morning,
    build_order,
    order_drivers,
)
from harabhara.decisions.surplus import Buyer
from harabhara.reasons.writer import Names
from harabhara.rules.engine import RulesEngine
from harabhara.rules.guardrails import Facts
from harabhara.settings import load_config
from harabhara.state.projection import Lot

CFG = load_config()
ENGINE = RulesEngine(CFG)
IST = ZoneInfo("Asia/Kolkata")
PROV = Provenance(model_version="m1", data_snapshot_id="d1", config_digest=CFG.digest)
NAMES = Names(
    product="coriander",
    unit="bunch",
    stores={"S01": "Jayanagar", "S03": "Koramangala", "D01": "Bellandur"},
    buyers={"B1": "Prime Pickle"},
)
TUESDAY = date(2026, 11, 3)


def series(**over: object) -> Series:
    base: dict[str, object] = {
        "store_id": "S01",
        "sku_id": "P13",
        "category": "Leafy greens",
        "product": "coriander",
        "unit": "bunch",
        "format": "Store",
        "price": 13.0,
        "unit_cost": 6.5,
        "life_days": 2,
        "festival_sensitive": False,
    }
    return Series(**{**base, **over})  # type: ignore[arg-type]


def order_inputs(**over: object) -> OrderInputs:
    base: dict[str, object] = {
        "series": series(),
        "on": TUESDAY,
        "demand": Range(low=85, likely=105, high=128),
        "stock": 51.0,
        "manager_units": 137.0,
        "thin_history": False,
        "weekend": False,
        "heavy_rain": False,
        "festival_eve_intensity": 0.0,
        "hot_day": False,
        "sold_out_at_origin": False,
        "last_day_stock": 0.0,
    }
    return OrderInputs(**{**base, **over})  # type: ignore[arg-type]


def _build(i: OrderInputs) -> tuple[Suggestion, Facts]:
    now = datetime(2026, 11, 2, 20, 30, tzinfo=IST)
    built = build_order(i, cfg=CFG, names=NAMES, prov=PROV, now=now)
    assert built is not None
    return built


def codes(i: OrderInputs) -> list[str]:
    return [d.code for d in order_drivers(i, CFG)]


# ---- evening orders ------------------------------------------------------------------------
def test_a_normal_day_still_gets_a_reason() -> None:
    assert codes(order_inputs(series=series(life_days=5))) == ["normal_day"]


def test_each_driver_appears_only_when_its_fact_is_true() -> None:
    assert "weekend" in codes(order_inputs(weekend=True))
    assert "weekend" not in codes(order_inputs(weekend=False))
    assert "sold_out_yesterday" in codes(order_inputs(sold_out_at_origin=True))
    assert "old_stock_lingers" in codes(order_inputs(last_day_stock=12.0))
    assert "two_day_life" in codes(order_inputs())
    assert "two_day_life" not in codes(order_inputs(series=series(life_days=4)))


def test_rain_is_down_for_walk_in_stores_and_up_for_dark_stores() -> None:
    assert "heavy_rain_walk_in" in codes(order_inputs(heavy_rain=True))
    dark = order_inputs(heavy_rain=True, series=series(store_id="D01", format="Dark store"))
    assert "heavy_rain_dark" in codes(dark)
    assert "heavy_rain_walk_in" not in codes(dark)


def test_a_festival_eve_lifts_sensitive_products_and_leaves_others_flat() -> None:
    eve = 1.0
    banana = order_inputs(
        series=series(sku_id="P04", festival_sensitive=True), festival_eve_intensity=eve
    )
    onion = order_inputs(
        series=series(sku_id="P02", festival_sensitive=False), festival_eve_intensity=eve
    )
    assert "festival_eve" in codes(banana)
    assert "festival_eve_flat" in codes(onion)
    assert "festival_eve" not in codes(onion)
    assert "festival_eve" not in codes(order_inputs(festival_eve_intensity=0.2))


def test_heat_only_counts_for_heat_sensitive_products() -> None:
    watermelon = order_inputs(series=series(sku_id="P11", life_days=6), hot_day=True)
    assert "hot_day" in codes(watermelon)
    assert "hot_day" not in codes(order_inputs(hot_day=True))


def test_thin_history_is_a_driver_and_comes_first_in_the_reason() -> None:
    i = order_inputs(thin_history=True, weekend=True)
    assert codes(i)[0] == "thin_history"
    suggestion, _ = _build(i)
    assert suggestion.reason.index("little history") < suggestion.reason.index("weekend")


def test_the_order_carries_a_range_the_manager_rule_and_one_sentence() -> None:
    suggestion, _ = _build(order_inputs())
    payload = suggestion.payload
    assert payload.kind == "order"
    assert payload.range.low <= payload.recommended_units <= payload.range.high
    assert payload.manager_rule_units == 137.0
    assert suggestion.reason.endswith(".")
    assert "\n" not in suggestion.reason


def test_ids_are_stable_so_loading_twice_changes_nothing() -> None:
    a, _ = _build(order_inputs())
    b, _ = _build(order_inputs())
    assert a.id == b.id == f"order:S01:P13:{TUESDAY}"


def test_the_order_deadline_is_the_evening_window_before_the_selling_day() -> None:
    suggestion, _ = _build(order_inputs())
    end = CFG.schedule.evening_order_window.end
    assert suggestion.deadline == datetime.combine(
        date(2026, 11, 2), time.fromisoformat(end), tzinfo=IST
    )
    assert suggestion.approver_role == "store_manager"


def test_every_evening_order_passes_the_guardrail_engine() -> None:
    for i in (
        order_inputs(),
        order_inputs(thin_history=True),
        order_inputs(weekend=True, heavy_rain=True, sold_out_at_origin=True),
        order_inputs(
            series=series(sku_id="P04", festival_sensitive=True), festival_eve_intensity=1.0
        ),
    ):
        suggestion, facts = _build(i)
        verdict = ENGINE.evaluate(suggestion, facts)
        assert verdict.allowed, [v.message for v in verdict.violations]


def test_more_stock_on_hand_means_a_smaller_order() -> None:
    low, _ = _build(order_inputs(stock=10.0))
    high, _ = _build(order_inputs(stock=80.0))
    assert high.payload.recommended_units < low.payload.recommended_units  # type: ignore[union-attr]


# ---- morning actions -----------------------------------------------------------------------
def _store(
    store_id: str, lots: list[Lot], demand: Range, delivered: float = 100.0, **over: object
) -> MorningStore:
    return MorningStore(
        series=series(
            store_id=store_id, sku_id="P20", category="Vegetables", product="beans",
            unit="kg", price=81.0, unit_cost=50.0, life_days=3, **over,
        ),
        lots=tuple(lots),
        demand=(demand, demand, demand),
        delivered_today=delivered,
        thin_history=False,
        opening="07:00",
    )  # fmt: skip


BEANS = Names(
    product="beans", unit="kg",
    stores={"S01": "Jayanagar", "S03": "Koramangala"}, buyers={"B1": "Prime Pickle"},
)  # fmt: skip
DEMAND = Range(low=40, likely=50, high=60)
NOW = datetime(2026, 11, 4, 7, 30, tzinfo=IST)


def _morning(stores: list[MorningStore], **over: object) -> list[tuple[Suggestion, Facts]]:
    args: dict[str, object] = {
        "as_of": date(2026, 11, 4),
        "now": NOW,
        "pairs": {("S01", "S03")},
        "buyers": [],
        "used_capacity": {},
        "names": BEANS,
        "cfg": CFG,
        "prov": PROV,
    }
    return build_morning(stores, **{**args, **over})  # type: ignore[arg-type]


def test_a_store_holding_too_much_and_a_neighbour_running_out_get_a_transfer() -> None:
    donor = _store("S01", [Lot(80, 1)], DEMAND)  # holds far more than it will sell
    receiver = _store("S03", [Lot(10, 3)], DEMAND)  # will run out
    out = _morning([donor, receiver])
    transfers = [s for s, _ in out if s.payload.kind == "transfer"]
    assert len(transfers) == 1
    t = transfers[0]
    assert (t.payload.from_store, t.payload.to_store) == ("S01", "S03")  # type: ignore[union-attr]
    assert t.approver_role == "area_manager"
    assert t.deadline.hour == CFG.rules.transfer.approve_by_hour
    assert "Koramangala" in t.reason
    assert t.id == "transfer:S01:S03:P20:2026-11-04"


def test_after_a_transfer_the_donor_is_not_also_told_to_mark_everything_down() -> None:
    out = _morning([_store("S01", [Lot(80, 1)], DEMAND), _store("S03", [Lot(10, 3)], DEMAND)])
    kinds = [s.payload.kind for s, _ in out]
    assert kinds.count("transfer") == 1
    assert "markdown" not in kinds


def test_without_a_neighbour_in_reach_the_expected_waste_is_marked_down_first() -> None:
    out = _morning([_store("S01", [Lot(90, 1)], DEMAND)], pairs=set())
    kinds = [s.payload.kind for s, _ in out]
    assert kinds[0] == "markdown"
    first = out[0][0]
    assert first.payload.step_pct == CFG.rules.markdown.step_1_pct  # type: ignore[union-attr]
    assert first.payload.start == "07:00"  # type: ignore[union-attr]


def test_a_markdown_of_most_of_the_delivery_goes_to_the_area_manager() -> None:
    out = _morning([_store("S01", [Lot(90, 1)], DEMAND, delivered=100.0)], pairs=set())
    assert out[0][0].approver_role == "area_manager"
    small = _morning([_store("S01", [Lot(90, 1)], DEMAND, delivered=1000.0)], pairs=set())
    assert small[0][0].approver_role == CFG.rules.markdown.approver_default


def test_what_a_markdown_will_not_sell_is_offered_to_a_buyer() -> None:
    buyer = Buyer(
        buyer_id="B1", buyer_type="Pickle and sauce maker", nearest_store="S01",
        skus=frozenset({"P20"}), grades=frozenset({"B", "C"}), price_share=0.35, max_units=100.0,
        window_start=time(21, 0), window_end=time(23, 0), notice_hours=2,
    )  # fmt: skip
    out = _morning([_store("S01", [Lot(90, 1)], DEMAND)], pairs=set(), buyers=[buyer])
    offers = [s for s, _ in out if s.payload.kind == "surplus"]
    assert len(offers) == 1
    assert offers[0].payload.buyer_id == "B1"  # type: ignore[union-attr]
    assert offers[0].deadline.hour == int(CFG.schedule.surplus_plan_confirm_by[:2])
    assert "Prime Pickle" in offers[0].reason


def test_a_quiet_morning_raises_no_alerts() -> None:
    quiet = _store("S01", [Lot(45, 3)], DEMAND)  # about what it will sell, plenty of life left
    assert _morning([quiet], pairs=set()) == []


def test_every_morning_suggestion_passes_the_guardrail_engine() -> None:
    buyer = Buyer(
        buyer_id="B1", buyer_type="Pickle and sauce maker", nearest_store="S01",
        skus=frozenset({"P20"}), grades=frozenset({"B", "C"}), price_share=0.35, max_units=100.0,
        window_start=time(21, 0), window_end=time(23, 0), notice_hours=2,
    )  # fmt: skip
    scenarios = [
        (
            [_store("S01", [Lot(80, 1)], DEMAND), _store("S03", [Lot(10, 3)], DEMAND)],
            {("S01", "S03")},
        ),
        ([_store("S01", [Lot(90, 1)], DEMAND)], set()),
        ([_store("S01", [Lot(40, 2), Lot(60, 1)], DEMAND)], set()),
    ]
    produced = 0
    for stores, pairs in scenarios:
        for suggestion, facts in _morning(stores, pairs=pairs, buyers=[buyer]):
            produced += 1
            verdict = ENGINE.evaluate(suggestion, facts)
            assert verdict.allowed, (suggestion.id, [v.message for v in verdict.violations])
    assert produced >= 4


def test_an_early_markdown_is_flagged_and_needs_two_days_of_life() -> None:
    out = _morning([_store("S01", [Lot(80, 2)], Range(low=10, likely=15, high=20))], pairs=set())
    early = [s for s, _ in out if s.payload.kind == "markdown" and s.payload.earlier_than_last_day]
    assert early, "a large expected leftover two days out should suggest an early markdown"
    assert all("expire" in s.reason for s in early)


def test_no_morning_suggestion_is_ever_past_its_last_sellable_day() -> None:
    for suggestion, facts in _morning([_store("S01", [Lot(90, 1)], DEMAND)], pairs=set()):
        assert facts.life_left_days is None or facts.life_left_days >= 1
        assert suggestion.state == "proposed"


@pytest.mark.parametrize("n", [0])
def test_nothing_is_built_for_no_stores(n: int) -> None:
    assert _morning([]) == []


def test_a_store_with_a_real_chance_of_running_out_is_helped_even_if_the_likely_case_is_fine() -> (
    None
):
    donor = _store("S01", [Lot(80, 1)], DEMAND)
    # likely demand (45) is below its 50 on hand, so the likely case shows no shortage, but the
    # tail (110) leaves it 60 short, which is an expected shortfall of 18 units
    receiver = _store("S03", [Lot(50, 3)], Range(low=30, likely=45, high=110))
    out = _morning([donor, receiver])
    transfers = [s for s, _ in out if s.payload.kind == "transfer"]
    assert len(transfers) == 1
    payload = transfers[0].payload
    assert isinstance(payload, TransferPayload)
    assert payload.to_store == "S03"
    assert 0 < payload.units <= 18.0 + 1e-6


def test_a_small_risk_is_not_worth_a_van_trip() -> None:
    donor = _store("S01", [Lot(80, 1)], DEMAND)
    receiver = _store("S03", [Lot(50, 3)], Range(low=30, likely=45, high=75))  # about 7 units
    out = _morning([donor, receiver])
    assert not [s for s, _ in out if s.payload.kind == "transfer"]


def test_a_last_day_markdown_and_a_day_early_markdown_never_share_an_id() -> None:
    """Both can be 30% from opening for the same store and product; the loader skips repeats."""
    lots = [Lot(60, 1), Lot(80, 2)]  # stock on its last day and stock a day behind it
    out = _morning([_store("S01", lots, Range(low=10, likely=15, high=20))], pairs=set())
    markdowns = [(s, s.payload) for s, _ in out if isinstance(s.payload, MarkdownPayload)]
    ids = [s.id for s, _ in markdowns]
    assert len(ids) == len(set(ids))
    early = [s for s, payload in markdowns if payload.earlier_than_last_day]
    standard = [s for s, payload in markdowns if not payload.earlier_than_last_day]
    assert early
    assert standard
    assert all(s.id.endswith(":early") for s in early)
    assert not any(s.id.endswith(":early") for s in standard)
