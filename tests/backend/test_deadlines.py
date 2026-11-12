"""A deadline that passes expires the suggestion; nothing else happens."""

from __future__ import annotations

from datetime import datetime, timedelta

from harabhara.contracts import MarkdownPayload
from harabhara.workflow.deadlines import aware, is_overdue
from tests.backend.conftest import IST, NOW, Env, decision_body, make_suggestion


def test_overdue_at_and_after_the_deadline() -> None:
    assert not is_overdue(NOW + timedelta(seconds=1), NOW)
    assert is_overdue(NOW, NOW)
    assert is_overdue(NOW - timedelta(seconds=1), NOW)


def test_naive_datetimes_are_read_as_kolkata() -> None:
    naive = datetime(2026, 11, 10, 21, 0)
    assert aware(naive).tzinfo is not None
    assert aware(naive) == naive.replace(tzinfo=IST)


def test_overdue_suggestion_expires_when_listed(strict_env: Env) -> None:
    strict_env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=30)))
    strict_env.clock.advance(minutes=31)
    r = strict_env.client.get("/api/v1/suggestions", headers=strict_env.login("1111"))
    assert [s["state"] for s in r.json()] == ["expired"]


def test_expiry_changes_only_the_state_and_writes_one_audit_event(strict_env: Env) -> None:
    original = make_suggestion(deadline=NOW + timedelta(minutes=30))
    strict_env.storage.create_suggestion(original)
    strict_env.clock.advance(hours=1)
    strict_env.client.get("/api/v1/suggestions/sg-1", headers=strict_env.login("1111"))
    strict_env.client.get(
        "/api/v1/suggestions/sg-1", headers=strict_env.login("1111")
    )  # repeat-safe
    stored = strict_env.storage.get_suggestion("sg-1")
    assert stored == original.model_copy(update={"state": "expired"})
    assert strict_env.storage.get_approval("sg-1") is None  # nobody decided; nothing was approved
    assert [e.type for e in strict_env.storage.list_audit("sg-1")] == ["expired"]


def test_a_decision_after_the_deadline_is_refused_and_expires_it(strict_env: Env) -> None:
    strict_env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=30)))
    headers = strict_env.login("1111")
    strict_env.clock.advance(minutes=31)
    r = strict_env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-1", "approve", "store_manager"),
        headers=headers,
    )
    assert r.status_code == 409
    stored = strict_env.storage.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "expired"
    assert strict_env.storage.get_approval("sg-1") is None


def test_a_decided_suggestion_does_not_expire(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=30)))
    env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-1", "approve", "store_manager"),
        headers=env.login("1111"),
    )
    env.clock.advance(hours=2)
    assert (
        env.client.get("/api/v1/suggestions/sg-1", headers=env.login("1111")).json()["state"]
        == "approved"
    )


# ---- the order timeout is switched off in the shipped config -----------------------------------


def test_with_the_timeout_off_an_evening_order_stays_open_past_its_deadline(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=30)))
    env.clock.advance(hours=6)
    r = env.client.get("/api/v1/suggestions", headers=env.login("1111"))
    assert [s["state"] for s in r.json()] == ["proposed"]
    assert env.storage.list_audit("sg-1") == []  # nothing expired, nothing logged


def test_with_the_timeout_off_a_late_decision_is_still_recorded(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=30)))
    headers = env.login("1111")
    env.clock.advance(hours=6)
    r = env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-1", "approve", "store_manager"),
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert env.storage.get_approval("sg-1") is not None  # still a person's recorded decision


def test_with_the_timeout_off_other_suggestions_still_expire(env: Env) -> None:
    """Only evening orders lose the timeout. A morning markdown still runs out at its deadline."""
    markdown = make_suggestion(
        "md-1",
        payload=MarkdownPayload(units=10, step_pct=30, start="07:00", expected_recovery_inr=100),
        deadline=NOW + timedelta(minutes=30),
    )
    env.storage.create_suggestion(markdown)
    env.clock.advance(hours=1)
    r = env.client.get("/api/v1/suggestions", headers=env.login("1111"))
    assert [s["state"] for s in r.json()] == ["expired"]


def test_with_the_timeout_on_an_evening_order_expires_at_its_deadline(strict_env: Env) -> None:
    strict_env.storage.create_suggestion(make_suggestion(deadline=NOW + timedelta(minutes=30)))
    strict_env.clock.advance(minutes=31)
    r = strict_env.client.get("/api/v1/suggestions", headers=strict_env.login("1111"))
    assert [s["state"] for s in r.json()] == ["expired"]
