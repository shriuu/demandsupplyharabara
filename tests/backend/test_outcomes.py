"""Outcomes: what really happened is entered by a person, scoped by role, and kept in the audit."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from harabhara.contracts import OutcomeRecord
from tests.backend.conftest import NOW, TODAY, Env, make_suggestion

V1 = "/api/v1"


def closing(**kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "closing",
        "on": TODAY.isoformat(),
        "store_id": "S1",
        "sku_id": "tomato",
        "units_sold": 8,
        "units_wasted": 1,
        "sold_out": False,
    }
    return body | kw


def purchase(**kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "purchase",
        "on": TODAY.isoformat(),
        "sku_id": "tomato",
        "units_bought": 40,
        "source": "spot",
    }
    return body | kw


def post(env: Env, pin: str, body: dict[str, Any]) -> Any:
    return env.client.post(f"{V1}/outcomes", json=body, headers=env.login(pin))


def test_a_store_manager_records_closing_for_their_own_store(env: Env) -> None:
    r = post(env, "1111", closing())
    assert r.status_code == 200, r.text
    assert r.json()["recorded_by"] == "mgr-s1"
    assert len(env.storage.list_outcomes()) == 1


def test_a_store_manager_cannot_record_another_store_or_a_purchase(env: Env) -> None:
    assert post(env, "1111", closing(store_id="S2")).status_code == 403
    assert post(env, "1111", purchase()).status_code == 403
    assert env.storage.list_outcomes() == []


def test_the_dc_lead_records_purchases_and_not_closing(env: Env) -> None:
    assert post(env, "4444", purchase()).status_code == 200
    assert post(env, "4444", closing()).status_code == 403


def test_other_roles_cannot_record(env: Env) -> None:
    assert post(env, "3333", closing()).status_code == 403
    assert post(env, "5555", purchase()).status_code == 403


def test_a_day_that_has_not_happened_yet_is_refused(env: Env) -> None:
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    assert post(env, "1111", closing(on=tomorrow)).status_code == 422


def test_a_closing_record_needs_its_numbers_and_a_purchase_its_source(env: Env) -> None:
    assert post(env, "1111", closing(units_sold=None)).status_code == 422
    assert post(env, "4444", purchase(source=None)).status_code == 422
    assert post(env, "1111", closing(units_sold=-1)).status_code == 422


def test_recording_twice_keeps_one_record_and_both_in_the_audit(env: Env) -> None:
    post(env, "1111", closing(units_sold=8))
    post(env, "1111", closing(units_sold=9))
    rows = env.storage.list_outcomes()
    assert [r.units_sold for r in rows] == [9]
    events = [e for e in env.storage.list_audit() if e.type == "outcome"]
    assert len(events) == 2
    assert {e.actor for e in events} == {"mgr-s1"}


def test_closing_an_approved_order_marks_it_done(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("sg-1", store="S1"))
    env.storage.transition("sg-1", "proposed", "approved")
    assert post(env, "1111", closing(suggestion_id="sg-1")).status_code == 200
    stored = env.storage.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "done"


def test_a_proposed_or_other_stores_order_is_not_touched(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("sg-1", store="S1"))
    assert post(env, "1111", closing(suggestion_id="sg-1")).status_code == 200
    first = env.storage.get_suggestion("sg-1")
    assert first is not None
    assert first.state == "proposed"
    env.storage.create_suggestion(make_suggestion("sg-2", store="S2"))
    env.storage.transition("sg-2", "proposed", "approved")
    post(env, "1111", closing(suggestion_id="sg-2"))
    other = env.storage.get_suggestion("sg-2")
    assert other is not None
    assert other.state == "approved"


def test_recording_works_while_suggestions_are_switched_off(env: Env) -> None:
    env.storage.set_kill_switch(True)
    assert post(env, "1111", closing()).status_code == 200


def test_reading_is_scoped_by_role(env: Env) -> None:
    post(env, "1111", closing())
    post(env, "4444", purchase())
    other = env.login("2222")
    mine = env.client.get(f"{V1}/outcomes", headers=env.login("1111")).json()
    assert [r["kind"] for r in mine] == ["closing"]
    assert (
        env.client.get(f"{V1}/outcomes?store_id=S2", headers=env.login("1111")).status_code == 403
    )
    assert env.client.get(f"{V1}/outcomes", headers=other).json() == []
    dc = env.client.get(f"{V1}/outcomes", headers=env.login("4444")).json()
    assert [r["kind"] for r in dc] == ["purchase"]
    area = env.client.get(f"{V1}/outcomes", headers=env.login("3333")).json()
    assert {r["kind"] for r in area} == {"closing", "purchase"}
    assert env.client.get(f"{V1}/outcomes", headers=env.login("5555")).status_code == 403
    assert env.client.get(f"{V1}/outcomes").status_code == 401


def test_the_contract_refuses_mixed_records() -> None:
    base: dict[str, Any] = {
        "on": NOW.date(),
        "sku_id": "TOMATO",
        "recorded_by": "x",
        "recorded_at": NOW,
    }
    with pytest.raises(ValueError, match="closing"):
        OutcomeRecord(kind="closing", store_id="S1", units_bought=3, source="spot", **base)
    with pytest.raises(ValueError, match="purchase"):
        OutcomeRecord(kind="purchase", store_id="S1", units_bought=3, source="spot", **base)


def test_the_area_manager_sees_a_scorecard_from_what_was_recorded(env: Env) -> None:
    assert env.client.get(f"{V1}/scorecard/recorded", headers=env.login("3333")).json() == []
    post(env, "1111", closing(units_sold=90, units_wasted=10, sold_out=True))
    post(env, "4444", purchase(units_bought=30, source="farmer_group"))
    post(env, "4444", purchase(units_bought=70, source="spot"))
    cards = env.client.get(f"{V1}/scorecard/recorded", headers=env.login("3333")).json()
    chain = next(c for c in cards if c["scope"] == "chain")
    assert chain["waste_pct"] == pytest.approx(10.0)
    assert chain["stockout_pct"] == pytest.approx(100.0)
    assert chain["farmer_share"] == pytest.approx(0.3)
    for pin in ("1111", "4444", "5555"):
        assert env.client.get(f"{V1}/scorecard/recorded", headers=env.login(pin)).status_code == 403


def test_the_scoreboard_lists_each_store_once_with_its_newest_period(env: Env) -> None:
    from harabhara.contracts import Scorecard

    def card(scope: str, end_offset: int, waste: float) -> Scorecard:
        return Scorecard(
            scope=scope,
            period_start=TODAY - timedelta(days=30 - end_offset),
            period_end=TODAY - timedelta(days=end_offset),
            waste_pct=waste,
            stockout_pct=2.0,
            farmer_share=0.4,
        )

    env.storage.put_scorecards([card("S1", 2, 9.0), card("S1", 0, 5.0), card("S2", 1, 4.0)])
    r = env.client.get(f"{V1}/scorecard", headers=env.login("3333"))
    assert r.status_code == 200
    got = {row["scope"]: row["waste_pct"] for row in r.json()}
    assert got == {"S1": 5.0, "S2": 4.0}
    assert len(r.json()) == 2
