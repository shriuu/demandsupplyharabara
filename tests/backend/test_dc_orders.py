"""The DC lead sees what the stores ordered, added up, and where the buying was done."""

from __future__ import annotations

from typing import Any

from tests.backend.conftest import TODAY, Env, decision_body, make_suggestion

V1 = "/api/v1"


def decide(
    env: Env, pin: str, sid: str, action: str, role: str = "store_manager", **extra: Any
) -> None:
    r = env.client.post(
        f"{V1}/suggestions/{sid}/decision",
        json=decision_body(sid, action, role, **extra),
        headers=env.login(pin),
    )
    assert r.status_code == 200, r.text


def orders(env: Env) -> dict[str, Any]:
    r = env.client.get(f"{V1}/dc/orders", headers=env.login("4444"))
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_adds_up_decided_orders_and_keeps_waiting_ones_apart(env: Env) -> None:
    for sid, store in (("o1", "S1"), ("o2", "S2"), ("o3", "S3"), ("o4", "S4")):
        env.storage.create_suggestion(make_suggestion(sid, store))
    decide(env, "1111", "o1", "approve")
    decide(env, "2222", "o2", "edit", edited_units=25, reason="slow market")
    out = orders(env)
    (tomato,) = out["products"]
    assert tomato["sku_id"] == "tomato"
    assert tomato["confirmed_units"] == 65  # 40 as suggested + 25 as the manager changed it
    assert tomato["waiting_units"] == 80  # two stores have not decided
    assert (tomato["stores_decided"], tomato["stores_waiting"], tomato["stores_rejected"]) == (
        2,
        2,
        0,
    )
    assert out["all_decided"] is False


def test_rejected_orders_add_nothing_and_all_decided_turns_true(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("o1", "S1"))
    env.storage.create_suggestion(make_suggestion("o2", "S2"))
    decide(env, "1111", "o1", "approve")
    decide(env, "2222", "o2", "reject")
    out = orders(env)
    (tomato,) = out["products"]
    assert (tomato["confirmed_units"], tomato["waiting_units"], tomato["stores_rejected"]) == (
        40,
        0,
        1,
    )
    assert out["all_decided"] is True


def test_nothing_ordered_is_an_empty_view_not_an_error(env: Env) -> None:
    out = orders(env)
    assert out["products"] == []
    assert out["on"] is None
    assert out["all_decided"] is False


def test_only_the_dc_lead_sees_it(env: Env) -> None:
    for pin, status in (("4444", 200), ("1111", 403), ("3333", 403), ("5555", 403)):
        assert env.client.get(f"{V1}/dc/orders", headers=env.login(pin)).status_code == status


def purchase(**kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "purchase",
        "on": TODAY.isoformat(),
        "sku_id": "tomato",
        "units_bought": 30,
        "source": "spot",
        "market": "K.R. Market",
    }
    return body | kw


def test_spot_buying_names_its_mandi_and_the_view_lists_it(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("o1", "S1"))
    dc = env.login("4444")
    for body in (
        purchase(),
        purchase(market="APMC Yeshwanthpur", units_bought=20),
        purchase(source="farmer_group", market=None, units_bought=50),
    ):
        assert env.client.post(f"{V1}/outcomes", json=body, headers=dc).status_code == 200
    bought = {(b["source"], b["market"]): b["units"] for b in orders(env)["bought"]}
    assert bought == {
        ("spot", "K.R. Market"): 30,
        ("spot", "APMC Yeshwanthpur"): 20,
        ("farmer_group", None): 50,
    }
    assert orders(env)["markets"] == ["APMC Yeshwanthpur", "K.R. Market"]


def test_a_market_we_do_not_buy_from_or_on_farmer_buying_is_refused(env: Env) -> None:
    dc = env.login("4444")
    unknown = env.client.post(f"{V1}/outcomes", json=purchase(market="Somewhere"), headers=dc)
    assert unknown.status_code == 422
    wrong = env.client.post(f"{V1}/outcomes", json=purchase(source="farmer_group"), headers=dc)
    assert wrong.status_code == 422
