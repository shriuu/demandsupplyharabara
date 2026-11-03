"""Role scoping: a store manager sees only their store; a role cannot call another's endpoints."""

from __future__ import annotations

import pytest

from tests.backend.conftest import (
    Env,
    farmer_row,
    make_forecast,
    make_suggestion,
    scorecard_row,
)

V1 = "/api/v1"

# endpoint -> the only roles (by PIN owner) allowed
ALLOWED = {
    "/forecasts": {"store_manager", "dc_lead"},
    "/dc/totals": {"dc_lead"},
    "/prices": {"dc_lead"},
    "/farmers/forecast": {"farmer_coordinator"},
    "/scorecard": {"area_manager"},
    "/audit": {"area_manager"},
}
PIN_ROLE = {
    "1111": "store_manager",
    "3333": "area_manager",
    "4444": "dc_lead",
    "5555": "farmer_coordinator",
}


@pytest.mark.parametrize("path", sorted(ALLOWED))
@pytest.mark.parametrize("pin", sorted(PIN_ROLE))
def test_each_endpoint_admits_only_its_roles(env: Env, path: str, pin: str) -> None:
    r = env.client.get(V1 + path, headers=env.login(pin))
    expected = 200 if PIN_ROLE[pin] in ALLOWED[path] else 403
    assert r.status_code == expected, (path, pin, r.text)


@pytest.mark.parametrize("path", [*sorted(ALLOWED), "/suggestions"])
def test_every_data_endpoint_needs_sign_in(env: Env, path: str) -> None:
    assert env.client.get(V1 + path).status_code == 401
    assert env.client.get(V1 + path, headers={"Authorization": "Bearer junk"}).status_code == 401


def test_store_manager_sees_only_their_store(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("a", store="S1"))
    env.storage.create_suggestion(make_suggestion("b", store="S2"))
    s1 = env.client.get(f"{V1}/suggestions", headers=env.login("1111")).json()
    assert [s["id"] for s in s1] == ["a"]
    assert env.client.get(f"{V1}/suggestions/b", headers=env.login("1111")).status_code == 404
    other = env.client.get(f"{V1}/suggestions?store_id=S2", headers=env.login("1111"))
    assert other.status_code == 403


def test_store_manager_forecasts_are_forced_to_their_store(env: Env) -> None:
    env.storage.put_forecasts([make_forecast("S1"), make_forecast("S2")])
    rows = env.client.get(f"{V1}/forecasts", headers=env.login("1111")).json()
    assert {r["store_id"] for r in rows} == {"S1"}
    assert (
        env.client.get(f"{V1}/forecasts?store_id=S2", headers=env.login("1111")).status_code == 403
    )
    both = env.client.get(f"{V1}/forecasts", headers=env.login("4444")).json()
    assert {r["store_id"] for r in both} == {"S1", "S2"}


def test_area_manager_sees_every_store_and_dc_lead_only_their_own_queue(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("a", store="S1"))
    env.storage.create_suggestion(make_suggestion("b", store="S2", approver="dc_lead"))
    area = env.client.get(f"{V1}/suggestions", headers=env.login("3333")).json()
    assert {s["id"] for s in area} == {"a", "b"}
    dc = env.client.get(f"{V1}/suggestions", headers=env.login("4444")).json()
    assert {s["id"] for s in dc} == {"b"}


def test_suggestions_are_most_urgent_first_and_filterable(env: Env) -> None:
    from datetime import timedelta

    from tests.backend.conftest import NOW

    env.storage.create_suggestion(make_suggestion("late", deadline=NOW + timedelta(hours=3)))
    env.storage.create_suggestion(make_suggestion("soon", deadline=NOW + timedelta(hours=1)))
    rows = env.client.get(f"{V1}/suggestions", headers=env.login("3333")).json()
    assert [s["id"] for s in rows] == ["soon", "late"]
    assert env.client.get(f"{V1}/suggestions?kind=transfer", headers=env.login("3333")).json() == []
    assert (
        len(env.client.get(f"{V1}/suggestions?state=proposed", headers=env.login("3333")).json())
        == 2
    )


def test_dc_totals_sum_the_ranges_across_stores(env: Env) -> None:
    env.storage.put_forecasts([make_forecast("S1"), make_forecast("S2")])
    body = env.client.get(f"{V1}/dc/totals", headers=env.login("4444")).json()
    (total,) = body["totals"]
    assert total["demand"] == {"low": 40, "likely": 60, "high": 90}
    assert total["stores"] == 2
    assert body["trimming"] == []  # nothing from the decision layer yet; nothing is invented


def test_farmer_forecast_is_labelled_estimate_and_scorecard_reports_all_three(env: Env) -> None:
    env.storage.put_farmer_forecasts([farmer_row()])
    env.storage.put_scorecards([scorecard_row()])
    farmers = env.client.get(f"{V1}/farmers/forecast", headers=env.login("5555")).json()
    assert [r["label"] for r in farmers] == ["estimate"]
    (card,) = env.client.get(f"{V1}/scorecard", headers=env.login("3333")).json()
    assert {"waste_pct", "stockout_pct", "farmer_share"} <= card.keys()


def test_assistant_only_answers_about_suggestions_the_user_may_see(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion("a", store="S1"))
    ask = {"suggestion_id": "a", "question": "why?"}
    ok = env.client.post(f"{V1}/assistant/ask", json=ask, headers=env.login("1111"))
    assert ok.status_code == 200
    assert ok.json()["source"] == "assistant"
    no = env.client.post(f"{V1}/assistant/ask", json=ask, headers=env.login("2222"))
    assert no.status_code == 404
    assert env.assistant.calls == [("a", "why?")]
