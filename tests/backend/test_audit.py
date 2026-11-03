"""The audit log is append-only and records every suggestion, decision and expiry."""

from __future__ import annotations

import pytest

from harabhara.api.storage import AlreadyExistsError, InMemoryStorage, Storage
from harabhara.contracts import AuditEvent
from tests.backend.conftest import NOW, Env, decision_body, make_suggestion


def test_storage_interface_has_no_way_to_change_or_delete_audit_or_approvals() -> None:
    names = {n for n in dir(Storage) if not n.startswith("_")}
    for forbidden in ("update_audit", "delete_audit", "update_approval", "delete_approval"):
        assert forbidden not in names
    audit_methods = {n for n in names if "audit" in n}
    assert audit_methods == {"append_audit", "list_audit"}


def test_a_repeated_audit_id_is_refused_not_overwritten() -> None:
    storage = InMemoryStorage()
    first = AuditEvent(id="e1", at=NOW, type="outcome", actor="a", data={"sold": 3})
    storage.append_audit(first)
    with pytest.raises(AlreadyExistsError):
        storage.append_audit(first.model_copy(update={"data": {"sold": 99}}))
    assert storage.list_audit() == [first]


def test_every_state_change_leaves_an_audit_event(env: Env) -> None:
    for i, (action, extra, event) in enumerate(
        [
            ("approve", {}, "approved"),
            ("edit", {"edited_units": 3, "reason": "short"}, "edited"),
            ("reject", {}, "rejected"),
        ]
    ):
        sid = f"sg-{i}"
        env.storage.create_suggestion(make_suggestion(sid))
        env.client.post(
            f"/api/v1/suggestions/{sid}/decision",
            json=decision_body(sid, action, "store_manager", **extra),
            headers=env.login("1111"),
        )
        events = env.storage.list_audit(sid)
        assert [e.type for e in events] == [event]
        assert events[0].actor == "mgr-s1"


def test_edit_audit_carries_units_and_reason(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-1", "edit", "store_manager", edited_units=7, reason="festival"),
        headers=env.login("1111"),
    )
    (event,) = env.storage.list_audit("sg-1")
    assert event.data["edited_units"] == 7
    assert event.data["reason"] == "festival"


def test_audit_endpoint_is_area_manager_only_and_read_only(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-1", "approve", "store_manager"),
        headers=env.login("1111"),
    )
    assert env.client.get("/api/v1/audit", headers=env.login("1111")).status_code == 403
    rows = env.client.get("/api/v1/audit?suggestion_id=sg-1", headers=env.login("3333")).json()
    assert [r["type"] for r in rows] == ["approved"]
    assert env.client.delete("/api/v1/audit", headers=env.login("3333")).status_code == 405
    assert env.client.put("/api/v1/audit", headers=env.login("3333")).status_code == 405
