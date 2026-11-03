"""G12: on any failure show less, mark it stale, and let the usual process carry on."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

from fastapi.testclient import TestClient

from harabhara.api.app import create_app
from harabhara.api.ports import FakeAssistant, FakePrices
from harabhara.api.settings import ApiSettings
from harabhara.api.storage import InMemoryStorage, Storage
from tests.backend.conftest import (
    NOW,
    PINS,
    TODAY,
    Clock,
    Env,
    decision_body,
    make_forecast,
    make_quote,
    make_suggestion,
)

V1 = "/api/v1"
STALE = "x-data-stale"


class BrokenStorage(InMemoryStorage):
    """Everything that reads or writes raises, as when Firestore is unreachable."""

    def _boom(self, *_: object, **__: object) -> None:
        raise ConnectionError("firestore unreachable")

    list_suggestions = get_suggestion = list_forecasts = list_prices = _boom  # type: ignore[assignment]
    list_audit = list_scorecards = list_farmer_forecasts = kill_switch_on = _boom  # type: ignore[assignment]
    transition = create_approval = append_audit = _boom  # type: ignore[assignment]


def broken_client() -> tuple[TestClient, dict[str, str]]:
    app = create_app(
        cast(Storage, BrokenStorage()),
        ApiSettings(signing_key="k", pins=PINS),
        prices=FakePrices(down=True),
        assistant=FakeAssistant(),
        clock=Clock(),
    )
    client = TestClient(app)
    token = client.post(f"{V1}/auth/login", json={"pin": "1111"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_storage_down_returns_less_marked_stale_not_an_error() -> None:
    client, headers = broken_client()
    r = client.get(f"{V1}/suggestions", headers=headers)
    assert r.status_code == 200
    assert r.json() == []
    assert r.headers[STALE] == "true"
    f = client.get(f"{V1}/forecasts", headers=headers)
    assert (f.status_code, f.json(), f.headers[STALE]) == (200, [], "true")


def test_storage_down_a_decision_is_refused_so_nothing_half_happens() -> None:
    client, headers = broken_client()
    r = client.post(
        f"{V1}/suggestions/sg-1/decision",
        json=decision_body("sg-1", "approve", "store_manager"),
        headers=headers,
    )
    assert r.status_code in (503, 423)


def test_health_degrades_and_behaves_as_killed_when_storage_is_down() -> None:
    client, _ = broken_client()
    assert client.get(f"{V1}/health").json() == {"status": "degraded", "kill_switch": True}


def test_fresh_data_is_not_marked_stale(env: Env) -> None:
    env.storage.put_forecasts([make_forecast()])
    r = env.client.get(f"{V1}/forecasts", headers=env.login("1111"))
    assert r.headers[STALE] == "false"
    assert len(r.json()) == 1


def test_forecasts_for_past_days_are_dropped_and_the_rest_marked_stale(env: Env) -> None:
    env.storage.put_forecasts(
        [make_forecast(on=TODAY), make_forecast(on=TODAY - timedelta(days=1))]
    )
    r = env.client.get(f"{V1}/forecasts", headers=env.login("1111"))
    assert [row["target_date"] for row in r.json()] == [TODAY.isoformat()]
    assert r.headers[STALE] == "true"


def test_price_feed_down_serves_the_last_prices_as_stale_never_invented(env: Env) -> None:
    headers = env.login("4444")
    live = env.client.get(f"{V1}/prices?sku_id=tomato", headers=headers)
    assert live.json()[0]["status"] == "ok"
    assert live.headers[STALE] == "false"

    env.prices.down = True
    down = env.client.get(f"{V1}/prices?sku_id=tomato", headers=headers)
    assert down.headers[STALE] == "true"
    assert [q["status"] for q in down.json()] == ["stale"]
    assert down.json()[0]["source"] == make_quote().source  # citation kept


def test_price_feed_down_with_nothing_stored_shows_no_price(env: Env) -> None:
    env.prices.down = True
    r = env.client.get(f"{V1}/prices", headers=env.login("4444"))
    assert r.json() == []
    assert r.headers[STALE] == "true"


def test_unavailable_quotes_carry_no_price(env: Env) -> None:
    env.prices.quotes = [make_quote("unavailable")]
    (q,) = env.client.get(f"{V1}/prices", headers=env.login("4444")).json()
    assert (q["status"], q["modal_inr"]) == ("unavailable", None)


def test_assistant_down_falls_back_to_the_stored_reason(env: Env) -> None:
    env.assistant.down = True
    env.storage.create_suggestion(make_suggestion())
    r = env.client.post(
        f"{V1}/assistant/ask",
        json={"suggestion_id": "sg-1", "question": "why?"},
        headers=env.login("1111"),
    )
    assert r.status_code == 200
    assert r.json()["source"] == "stored_reason"
    assert r.json()["answer"] == make_suggestion().reason


def test_a_failed_expiry_pass_does_not_break_reading(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(hours=1)))

    def boom(*_: object) -> bool:
        raise ConnectionError

    env.storage.transition = boom  # type: ignore[method-assign,assignment]
    env.clock.advance(hours=2)
    r = env.client.get(f"{V1}/suggestions", headers=env.login("1111"))
    assert r.status_code == 200


def test_unconfigured_ports_fail_safe() -> None:
    storage = InMemoryStorage()
    storage.create_suggestion(make_suggestion())
    app = create_app(storage, ApiSettings(signing_key="k", pins=PINS), clock=Clock())
    client = TestClient(app)

    def head(pin: str) -> dict[str, str]:
        t = client.post(f"{V1}/auth/login", json={"pin": pin}).json()["token"]
        return {"Authorization": f"Bearer {t}"}

    assert client.get(f"{V1}/prices", headers=head("4444")).json() == []
    ask = {"suggestion_id": "sg-1", "question": "why?"}
    assert client.post(f"{V1}/assistant/ask", json=ask, headers=head("1111")).json()["source"] == (
        "stored_reason"
    )


def test_sign_in_not_configured_is_a_clear_503_not_open_access() -> None:
    app = create_app(InMemoryStorage(), ApiSettings(), clock=Clock())
    client = TestClient(app)
    assert client.post(f"{V1}/auth/login", json={"pin": "1111"}).status_code == 503
    assert client.get(f"{V1}/suggestions", headers={"Authorization": "Bearer x"}).status_code == 503
    assert client.get(f"{V1}/health").status_code == 200
