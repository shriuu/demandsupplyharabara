"""The last seven days: a store manager sees their own store, an area manager store summaries."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from tests.backend.conftest import TODAY, Env, decision_body, make_suggestion

V1 = "/api/v1"


def history(env: Env, pin: str) -> Any:
    return env.client.get(f"{V1}/history/week", headers=env.login(pin))


def close(env: Env, pin: str, store: str, sku: str, sold: float, wasted: float, out: bool) -> None:
    r = env.client.post(
        f"{V1}/outcomes",
        json={
            "kind": "closing", "on": TODAY.isoformat(), "store_id": store, "sku_id": sku,
            "units_sold": sold, "units_wasted": wasted, "sold_out": out,
        },
        headers=env.login(pin),
    )  # fmt: skip
    assert r.status_code == 200, r.text


def test_a_store_manager_sees_only_their_store_for_seven_days_with_the_lines(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("o1", "S1"))
    env.storage.create_suggestion(make_suggestion("o2", "S2"))
    env.client.post(
        f"{V1}/suggestions/o1/decision",
        json=decision_body("o1", "edit", "store_manager", edited_units=25, reason="slow"),
        headers=env.login("1111"),
    )
    close(env, "1111", "S1", "tomato", 80, 20, True)
    r = history(env, "1111")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["store_id"] for s in body["stores"]] == ["S1"]
    days = body["stores"][0]["days"]
    assert len(days) == 7
    assert days[-1]["on"] == TODAY.isoformat()
    last = days[-1]
    assert last["orders_edited"] == 1
    assert last["units_confirmed"] == 25
    assert last["orders"][0]["suggested_units"] == 40
    assert last["orders"][0]["final_units"] == 25
    assert (last["waste_pct"], last["stockout_pct"]) == (20.0, 100.0)
    assert days[0]["waste_pct"] is None  # nothing recorded: unknown, not zero
    assert body["stores"][0]["days_with_closing"] == 1


def test_a_store_never_sees_another_store(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("o2", "S2"))
    body = history(env, "1111").json()
    assert all(d["orders_made"] == 0 for d in body["stores"][0]["days"])


def test_an_area_manager_gets_store_summaries_without_the_lines(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("o1", "S1"))
    close(env, "1111", "S1", "tomato", 90, 10, False)
    body = history(env, "3333").json()
    assert body[
        "farmer_share_definition"
    ]  # farmer share is always explained, never silently absent
    store = next(s for s in body["stores"] if s["store_id"] == "S1")
    assert store["waste_pct"] == 10.0
    assert store["stockout_pct"] == 0.0
    assert all(d["orders"] == [] and d["closing"] == [] for d in store["days"])


def test_other_roles_are_refused(env: Env) -> None:
    assert history(env, "4444").status_code == 403
    assert history(env, "5555").status_code == 403


def test_old_orders_fall_out_after_a_week(env: Env) -> None:
    old = make_suggestion("old", "S1")
    env.storage.create_suggestion(
        old.model_copy(update={"created_at": old.created_at - timedelta(days=9)})
    )
    body = history(env, "1111").json()
    assert sum(d["orders_made"] for d in body["stores"][0]["days"]) == 0
