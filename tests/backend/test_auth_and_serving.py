"""PIN sign-in, token handling and the static web app."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from harabhara.api.app import create_app
from harabhara.api.auth import Authenticator
from harabhara.api.settings import ApiSettings, from_env, parse_pins
from harabhara.api.storage import InMemoryStorage
from tests.backend.conftest import PINS, Clock, Env

V1 = "/api/v1"


def test_login_returns_role_and_store(env: Env) -> None:
    r = env.client.post(f"{V1}/auth/login", json={"pin": "1111"})
    assert r.status_code == 200
    assert (r.json()["role"], r.json()["store_id"]) == ("store_manager", "S1")


def test_wrong_pin_is_401_and_repeated_failures_are_throttled(env: Env) -> None:
    codes = [
        env.client.post(f"{V1}/auth/login", json={"pin": "0000"}).status_code for _ in range(7)
    ]
    assert codes[:5] == [401] * 5
    assert codes[5:] == [429, 429]
    # even the right PIN waits while throttled
    assert env.client.post(f"{V1}/auth/login", json={"pin": "1111"}).status_code == 429


def test_throttle_clears_after_the_window() -> None:
    now = [1000.0]
    auth = Authenticator(ApiSettings(signing_key="k", pins=PINS), lambda: now[0])
    for _ in range(5):
        with pytest.raises(Exception, match="wrong PIN"):
            auth.login("0000", "c")
    now[0] += 61
    token, user = auth.login("1111", "c")
    assert user.role == "store_manager"
    assert auth.verify(token) == user


def test_tampered_and_expired_tokens_are_refused() -> None:
    now = [1000.0]
    settings = ApiSettings(signing_key="k", pins=PINS, token_ttl_seconds=60)
    auth = Authenticator(settings, lambda: now[0])
    token, _ = auth.login("1111", "c")
    body, sig = token.split(".")
    with pytest.raises(Exception, match="bad signature"):
        auth.verify(f"{body}.{sig[::-1]}")
    forged = Authenticator(ApiSettings(signing_key="other", pins=PINS), lambda: now[0])
    with pytest.raises(Exception, match="bad signature"):
        forged.verify(token)
    now[0] += 61
    with pytest.raises(Exception, match="expired"):
        auth.verify(token)


def test_pin_directory_parsing() -> None:
    users = parse_pins(json.dumps({"1": {"actor_id": "a", "role": "dc_lead"}}))
    assert users["1"].role == "dc_lead"
    with pytest.raises(ValueError, match="store_id"):
        parse_pins(json.dumps({"1": {"actor_id": "a", "role": "store_manager"}}))
    with pytest.raises(ValueError, match="unknown role"):
        parse_pins(json.dumps({"1": {"actor_id": "a", "role": "boss"}}))


def test_settings_from_env_without_secrets_means_sign_in_not_ready() -> None:
    assert not from_env({}).sign_in_ready
    ready = from_env(
        {
            "HARABHARA_SIGNING_KEY": "k",
            "HARABHARA_PIN_DIRECTORY": json.dumps({"1": {"actor_id": "a", "role": "dc_lead"}}),
        }
    )
    assert ready.sign_in_ready


def static_client(tmp_path: Path) -> TestClient:
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("nope")
    settings = ApiSettings(signing_key="k", pins=PINS, static_dir=tmp_path)
    return TestClient(create_app(InMemoryStorage(), settings, clock=Clock()))


def test_serves_the_built_web_app_with_spa_fallback(tmp_path: Path) -> None:
    client = static_client(tmp_path)
    assert client.get("/").text == "<html>app</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/store/orders").text == "<html>app</html>"  # client-side route
    assert client.get(f"{V1}/health").json()["status"] == "ok"


def test_static_serving_cannot_escape_the_directory_or_shadow_the_api(tmp_path: Path) -> None:
    client = static_client(tmp_path)
    assert "nope" not in client.get("/..%2Fsecret.txt").text
    assert "nope" not in client.get("/../secret.txt").text
    assert client.get(f"{V1}/does-not-exist").status_code == 404


def test_without_a_built_app_the_api_still_runs(tmp_path: Path) -> None:
    settings = ApiSettings(signing_key="k", pins=PINS, static_dir=tmp_path)  # no index.html
    client = TestClient(create_app(InMemoryStorage(), settings, clock=Clock()))
    assert client.get("/").status_code == 404
    assert client.get(f"{V1}/health").status_code == 200


def test_demo_accounts_are_hidden_unless_switched_on() -> None:
    off = TestClient(create_app(InMemoryStorage(), ApiSettings(signing_key="k", pins=PINS)))
    assert off.get(f"{V1}/auth/demo").status_code == 404


def test_demo_accounts_list_every_sign_in_when_switched_on() -> None:
    settings = ApiSettings(signing_key="k", pins=PINS, demo_login=True)
    on = TestClient(create_app(InMemoryStorage(), settings))
    body = on.get(f"{V1}/auth/demo").json()
    assert {a["pin"] for a in body["accounts"]} == set(PINS)
    assert {a["role"] for a in body["accounts"]} == {u.role for u in PINS.values()}


def test_demo_accounts_stay_off_while_sign_in_is_not_ready() -> None:
    settings = ApiSettings(signing_key=None, pins=PINS, demo_login=True)
    assert (
        TestClient(create_app(InMemoryStorage(), settings)).get(f"{V1}/auth/demo").status_code
        == 404
    )
