"""The kill switch stops suggestions; the manual process carries on (guardrail 12)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from harabhara.api.loader import load_directory
from tests.backend.conftest import (
    NOW,
    TODAY,
    Env,
    decision_body,
    make_forecast,
    make_projection,
    make_suggestion,
    make_trimming,
)

KILL = "/api/v1/admin/kill-switch"


def test_only_the_area_manager_can_flip_it(env: Env) -> None:
    for pin in ("1111", "4444", "5555"):
        assert env.client.post(KILL, json={"on": True}, headers=env.login(pin)).status_code == 403
    assert not env.storage.kill_switch_on()
    assert env.client.post(KILL, json={"on": True}, headers=env.login("3333")).status_code == 200
    assert env.storage.kill_switch_on()


def test_health_reports_it_without_signing_in(env: Env) -> None:
    env.client.post(KILL, json={"on": True}, headers=env.login("3333"))
    assert env.client.get("/api/v1/health").json() == {"status": "ok", "kill_switch": True}


def test_switching_it_on_hides_proposals_and_blocks_decisions(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    env.client.post(KILL, json={"on": True}, headers=env.login("3333"))
    headers = env.login("1111")
    assert env.client.get("/api/v1/suggestions", headers=headers).json() == []
    assert env.client.get("/api/v1/suggestions/sg-1", headers=headers).status_code == 404
    r = env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-1", "approve", "store_manager"),
        headers=headers,
    )
    assert r.status_code == 423
    stored = env.storage.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "proposed"


def test_switching_it_off_restores_them(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    env.client.post(KILL, json={"on": True}, headers=env.login("3333"))
    env.client.post(KILL, json={"on": False}, headers=env.login("3333"))
    assert len(env.client.get("/api/v1/suggestions", headers=env.login("1111")).json()) == 1


def test_no_new_suggestion_is_loaded_while_it_is_on(env: Env, tmp_path: Path) -> None:
    (tmp_path / "suggestions.json").write_text(f"[{make_suggestion().model_dump_json()}]")
    (tmp_path / "forecasts.json").write_text(f"[{make_forecast().model_dump_json()}]")
    env.storage.set_kill_switch(True)
    report = load_directory(env.storage, tmp_path, NOW)
    assert report.suggestions_blocked_by_kill_switch == 1
    assert report.suggestions_created == 0
    assert env.storage.list_suggestions() == []
    assert len(env.storage.list_forecasts()) == 1  # forecasts are information, not suggestions


def test_flipping_it_is_audited(env: Env) -> None:
    env.client.post(KILL, json={"on": True}, headers=env.login("3333"))
    (event,) = env.storage.list_audit()
    assert (event.type, event.actor, event.data) == ("kill_switch", "area-1", {"on": True})


def test_expiry_still_runs_while_it_is_on(strict_env: Env) -> None:
    strict_env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=5)))
    strict_env.client.post(KILL, json={"on": True}, headers=strict_env.login("3333"))
    strict_env.clock.advance(minutes=10)
    strict_env.client.get("/api/v1/suggestions", headers=strict_env.login("1111"))
    stored = strict_env.storage.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "expired"


def test_trimming_advice_is_a_suggestion_so_the_switch_hides_it(env: Env) -> None:
    env.storage.put_forecasts([make_forecast()])
    env.storage.put_trimming([make_trimming()])
    env.client.post(KILL, json={"on": True}, headers=env.login("3333"))
    body = env.client.get("/api/v1/dc/totals", headers=env.login("4444")).json()
    assert len(body["totals"]) == 1  # information still shows
    assert body["trimming"] == []


def test_no_trimming_is_loaded_while_it_is_on_but_projections_are(env: Env, tmp_path: Path) -> None:
    (tmp_path / "trimming.json").write_text(f"[{make_trimming().model_dump_json()}]")
    (tmp_path / "projections.json").write_text(f"[{make_projection().model_dump_json()}]")
    env.storage.set_kill_switch(True)
    report = load_directory(env.storage, tmp_path, NOW)
    assert report.trimming_blocked_by_kill_switch == 1
    assert env.storage.list_trimming(TODAY) == []
    assert report.projections == 1
    assert len(env.storage.list_projections()) == 1
