"""Three area managers, each with their own stores. An area never sees or decides outside it."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from harabhara.api.app import create_app
from harabhara.api.ports import FakeAssistant, FakePrices
from harabhara.api.settings import ApiSettings, User, parse_pins
from harabhara.api.storage import InMemoryStorage
from harabhara.contracts import MarkdownPayload, Scorecard
from harabhara.settings.areas import load_areas
from tests.backend.conftest import NOW, TODAY, Clock, decision_body, make_suggestion

V1 = "/api/v1"
PINS = {
    "1111": User("head", "area_manager"),
    "6666": User("area-n", "area_manager", None, "north"),
    "7777": User("area-e", "area_manager", None, "east"),
    "8888": User("dc-1", "dc_lead"),
}
NORTH, EAST = "S06", "S05"  # a store in each area, as config/areas.yaml groups them


def build() -> tuple[TestClient, InMemoryStorage]:
    storage = InMemoryStorage()
    settings = ApiSettings(signing_key="k", pins=PINS)
    app = create_app(
        storage, settings, prices=FakePrices([]), assistant=FakeAssistant(), clock=Clock()
    )
    return TestClient(app), storage


def login(client: TestClient, pin: str) -> dict[str, str]:
    r = client.post(f"{V1}/auth/login", json={"pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def markdown(sid: str, store: str) -> Any:
    payload = MarkdownPayload(units=10, step_pct=30, start="07:00", expected_recovery_inr=100)
    return make_suggestion(sid, store, approver="area_manager", payload=payload)


def test_the_shipped_areas_cover_every_store_exactly_once() -> None:
    areas = load_areas()
    stores = [s for a in areas.values() for s in a.stores]
    assert len(areas) == 3
    assert sorted(stores) == sorted(set(stores))
    every = {f"S0{i}" for i in range(1, 9)} | {"D01", "D02", "D03", "D04"}
    assert set(stores) == every


def test_a_store_in_two_areas_is_refused(tmp_path: Path) -> None:
    (tmp_path / "areas.yaml").write_text(
        "areas:\n  a: {name: A, stores: [S1, S2]}\n  b: {name: B, stores: [S2]}\n"
    )
    with pytest.raises(ValueError, match="S2"):
        load_areas(tmp_path)


def test_login_says_which_area_and_a_made_up_area_stops_the_app() -> None:
    client, _ = build()
    r = client.post(f"{V1}/auth/login", json={"pin": "6666"})
    assert (r.json()["area_id"], r.json()["area_name"]) == ("north", "North")
    assert client.post(f"{V1}/auth/login", json={"pin": "1111"}).json()["area_id"] is None
    bad = ApiSettings(signing_key="k", pins={"9": User("x", "area_manager", None, "nowhere")})
    with pytest.raises(ValueError, match="nowhere"):
        create_app(InMemoryStorage(), bad)


def test_only_an_area_manager_can_have_an_area() -> None:
    raw = '{"1": {"actor_id": "m", "role": "store_manager", "store_id": "S1", "area_id": "north"}}'
    with pytest.raises(ValueError, match="area_manager"):
        parse_pins(raw)


def test_an_area_sees_and_decides_only_its_own_stores() -> None:
    client, storage = build()
    for sid, store in (("n1", NORTH), ("e1", EAST)):
        storage.create_suggestion(markdown(sid, store))
    north = login(client, "6666")
    ids = [s["id"] for s in client.get(f"{V1}/suggestions", headers=north).json()]
    assert ids == ["n1"]
    head = login(client, "1111")
    assert sorted(s["id"] for s in client.get(f"{V1}/suggestions", headers=head).json()) == [
        "e1",
        "n1",
    ]
    other = client.post(
        f"{V1}/suggestions/e1/decision",
        json=decision_body("e1", "approve", "area_manager"),
        headers=north,
    )
    assert other.status_code == 404
    own = client.post(
        f"{V1}/suggestions/n1/decision",
        json=decision_body("n1", "approve", "area_manager"),
        headers=north,
    )
    assert own.status_code == 200
    assert storage.get_suggestion("e1").state == "proposed"  # type: ignore[union-attr]


def card(scope: str) -> Scorecard:
    return Scorecard(
        scope=scope,
        period_start=TODAY - timedelta(days=28),
        period_end=TODAY,
        waste_pct=5.0,
        stockout_pct=2.0,
        farmer_share=0.4,
    )


def test_an_area_sees_scoreboards_for_its_stores_and_no_chain_wide_one() -> None:
    client, storage = build()
    storage.put_scorecards([card("chain"), card(NORTH), card(EAST)])
    north = client.get(f"{V1}/scorecard", headers=login(client, "6666")).json()
    assert [c["scope"] for c in north] == [NORTH]
    head = client.get(f"{V1}/scorecard", headers=login(client, "1111")).json()
    assert sorted(c["scope"] for c in head) == sorted(["chain", NORTH, EAST])


def test_only_the_all_stores_manager_can_stop_every_suggestion() -> None:
    client, _ = build()
    body = {"on": True}
    assert (
        client.post(f"{V1}/admin/kill-switch", json=body, headers=login(client, "6666")).status_code
        == 403
    )
    assert (
        client.post(f"{V1}/admin/kill-switch", json=body, headers=login(client, "1111")).status_code
        == 200
    )


def test_an_area_cannot_read_another_areas_records_or_audit() -> None:
    client, storage = build()
    storage.create_suggestion(markdown("e1", EAST))
    storage.create_suggestion(markdown("n1", NORTH))
    north = login(client, "6666")
    assert client.get(f"{V1}/outcomes?store_id={EAST}", headers=north).status_code == 403
    assert client.get(f"{V1}/outcomes?store_id={NORTH}", headers=north).status_code == 200
    events = client.get(f"{V1}/audit", headers=north)
    if events.status_code == 200:
        assert {e["suggestion_id"] for e in events.json()} <= {"n1"}


def test_the_dc_lead_is_not_limited_by_area() -> None:
    client, _ = build()
    assert client.get(f"{V1}/dc/orders", headers=login(client, "8888")).status_code == 200
    assert NOW  # clock fixed for the whole module
