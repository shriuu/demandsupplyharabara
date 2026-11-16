"""What a store manager does shows up for the area manager and the DC buying lead."""

from __future__ import annotations

from typing import Any

from harabhara.contracts import MarkdownPayload
from tests.backend.conftest import Env, decision_body, make_suggestion
from tests.backend.test_outcomes import closing, post

V1 = "/api/v1"


def get(env: Env, pin: str, path: str) -> Any:
    r = env.client.get(f"{V1}{path}", headers=env.login(pin))
    assert r.status_code == 200, r.text
    return r.json()


def test_an_order_decision_reaches_the_dc_lead_and_the_area_manager_sees_the_store_record(
    env: Env,
) -> None:
    env.storage.create_suggestion(make_suggestion("order-s1", "S1"))
    env.storage.create_suggestion(make_suggestion("order-s2", "S2"))

    # store manager 1 approves, store manager 2 changes the amount with a reason
    sid = "order-s1"
    r = env.client.post(
        f"{V1}/suggestions/{sid}/decision",
        json=decision_body(sid, "approve", "store_manager"),
        headers=env.login("1111"),
    )
    assert r.status_code == 200, r.text
    sid = "order-s2"
    r = env.client.post(
        f"{V1}/suggestions/{sid}/decision",
        json=decision_body(sid, "edit", "store_manager", edited_units=25, reason="slow day"),
        headers=env.login("2222"),
    )
    assert r.status_code == 200, r.text

    # the DC buying lead sees both, added up, as the managers decided
    (tomato,) = get(env, "4444", "/dc/orders")["products"]
    assert tomato["confirmed_units"] == 65  # 40 as suggested, 25 as changed
    assert tomato["stores_decided"] == 2

    # a closing count from store 1 shows in the area manager's week, and not in another store's
    assert post(env, "1111", closing()).status_code == 200
    week = get(env, "3333", "/history/week")
    by_store = {s["store_id"]: s for s in week["stores"]}
    assert by_store["S1"]["days_with_closing"] == 1
    assert by_store["S2"]["days_with_closing"] == 0
    assert by_store["S1"]["orders_decided"] >= 1
    # farmer share is the DC lead's alone
    assert "farmer" not in str(week).lower()


def test_a_markdown_for_the_area_manager_does_not_reach_the_store_queue_or_the_dc_orders(
    env: Env,
) -> None:
    env.storage.create_suggestion(
        make_suggestion(
            "md-1",
            "S1",
            approver="area_manager",
            payload=MarkdownPayload(
                step_pct=20, start="16:00", units=12, expected_recovery_inr=300
            ),
        )
    )
    waiting = get(env, "3333", "/suggestions?role=area_manager&state=proposed")
    assert [s["id"] for s in waiting] == ["md-1"]
    assert get(env, "1111", "/suggestions?role=store_manager&state=proposed") == []
    assert get(env, "4444", "/dc/orders")["products"] == []
