"""G01: a person approves every order, discount and transfer; nothing acts alone."""

from __future__ import annotations

import pytest
from httpx import Response

from harabhara.contracts import Approval, MarkdownPayload, TransferPayload
from harabhara.settings import load_config
from harabhara.workflow.approvals import (
    TRANSITIONS,
    DecisionError,
    assert_manual_only,
    next_state,
)
from tests.backend.conftest import NOW, Env, decision_body, make_suggestion


def decide(env: Env, pin: str, sid: str, action: str, role: str, **extra: object) -> Response:
    response: Response = env.client.post(
        f"/api/v1/suggestions/{sid}/decision",
        json=decision_body(sid, action, role, **extra),
        headers=env.login(pin),
    )
    return response


@pytest.mark.parametrize(
    ("action", "extra", "state"),
    [
        ("approve", {}, "approved"),
        ("edit", {"edited_units": 25, "reason": "rain cut footfall"}, "edited"),
        ("reject", {}, "rejected"),
    ],
)
def test_each_decision_moves_the_state(
    env: Env, action: str, extra: dict[str, object], state: str
) -> None:
    env.storage.create_suggestion(make_suggestion())
    r = decide(env, "1111", "sg-1", action, "store_manager", **extra)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == state
    stored = env.storage.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == state


def test_edit_without_units_or_reason_is_refused() -> None:
    with pytest.raises(ValueError, match="reason"):
        Approval(
            suggestion_id="sg-1",
            action="edit",
            actor_role="store_manager",
            actor_id="a",
            at=NOW,
            edited_units=5,
        )


def test_edit_without_reason_over_the_api_is_422(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    r = decide(env, "1111", "sg-1", "edit", "store_manager", edited_units=5)
    assert r.status_code == 422
    stored = env.storage.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "proposed"


def test_edit_records_units_and_reason(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    decide(env, "1111", "sg-1", "edit", "store_manager", edited_units=25, reason="rain")
    approval = env.storage.get_approval("sg-1")
    assert approval is not None
    assert (approval.edited_units, approval.reason) == (25, "rain")


def test_who_and_when_come_from_the_sign_in_not_the_caller(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    decide(env, "1111", "sg-1", "approve", "store_manager", actor_id="someone-else")
    approval = env.storage.get_approval("sg-1")
    assert approval is not None
    assert approval.actor_id == "mgr-s1"
    assert approval.at == env.clock.now


@pytest.mark.parametrize("first", ["approve", "reject"])
def test_a_decided_suggestion_cannot_be_decided_again(env: Env, first: str) -> None:
    env.storage.create_suggestion(make_suggestion())
    assert decide(env, "1111", "sg-1", first, "store_manager").status_code == 200
    again = decide(env, "1111", "sg-1", "approve", "store_manager")
    assert again.status_code == 409


def test_only_the_approver_role_can_decide(env: Env) -> None:
    env.storage.create_suggestion(
        make_suggestion(
            "tr-1",
            approver="area_manager",
            payload=TransferPayload(
                from_store="S1", to_store="S2", units=10, leave_by="10:00", van_cost_inr=500
            ),
        )
    )
    # the store manager can see it but is not the approver
    assert decide(env, "1111", "tr-1", "approve", "store_manager").status_code == 403
    # the DC lead cannot even see it
    assert decide(env, "4444", "tr-1", "approve", "dc_lead").status_code == 404
    assert decide(env, "3333", "tr-1", "approve", "area_manager").status_code == 200


def test_actor_role_must_match_the_sign_in(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    r = decide(env, "1111", "sg-1", "approve", "area_manager")
    assert r.status_code == 403


def test_body_and_path_must_name_the_same_suggestion(env: Env) -> None:
    env.storage.create_suggestion(make_suggestion())
    r = env.client.post(
        "/api/v1/suggestions/sg-1/decision",
        json=decision_body("sg-2", "approve", "store_manager"),
        headers=env.login("1111"),
    )
    assert r.status_code == 422


def test_approving_changes_only_the_state_never_the_payload(env: Env) -> None:
    md = make_suggestion(
        "md-1",
        payload=MarkdownPayload(units=12, step_pct=15, start="18:00", expected_recovery_inr=300),
    )
    env.storage.create_suggestion(md)
    decide(env, "1111", "md-1", "approve", "store_manager")
    stored = env.storage.get_suggestion("md-1")
    assert stored == md.model_copy(update={"state": "approved"})


def test_state_machine_final_states_have_no_exits_except_done() -> None:
    assert TRANSITIONS["rejected"] == frozenset()
    assert TRANSITIONS["expired"] == frozenset()
    assert TRANSITIONS["done"] == frozenset()
    assert TRANSITIONS["approved"] == {"done"}
    assert TRANSITIONS["edited"] == {"done"}


def test_next_state_refuses_a_decision_on_a_non_proposed_suggestion() -> None:
    s = make_suggestion().model_copy(update={"state": "expired"})
    a = Approval(
        suggestion_id="sg-1", action="approve", actor_role="store_manager", actor_id="a", at=NOW
    )
    with pytest.raises(DecisionError):
        next_state(s, a, NOW)


def test_the_only_state_changing_routes_are_the_documented_ones(env: Env) -> None:
    """No route can order, reprice or move stock: every non-GET route is listed here."""
    routes = {
        (method.upper(), path)
        for path, ops in env.app.openapi()["paths"].items()
        for method in ops
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}
    }
    assert routes == {
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/admin/kill-switch"),
        ("POST", "/api/v1/suggestions/{suggestion_id}/decision"),
        ("POST", "/api/v1/assistant/ask"),
        ("POST", "/api/v1/outcomes"),  # a person enters what happened; moves nothing
    }


def test_service_refuses_to_start_if_config_allows_automatic_action() -> None:
    cfg = load_config()
    assert_manual_only(cfg)  # the shipped config is manual only
    automatic = cfg.model_copy(
        update={
            "rules": cfg.rules.model_copy(
                update={
                    "automation": cfg.rules.automation.model_copy(
                        update={"auto_order_allowed": True}
                    )
                }
            )
        }
    )
    with pytest.raises(RuntimeError, match="without approval"):
        assert_manual_only(automatic)
