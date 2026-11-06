"""Builders for the append-only audit log. Events are created, never updated or deleted."""

from __future__ import annotations

import uuid
from datetime import datetime

from harabhara.contracts import Approval, AuditEvent, OutcomeRecord, Suggestion

_ACTION_EVENT = {"approve": "approved", "edit": "edited", "reject": "rejected"}


def _new_id() -> str:
    return uuid.uuid4().hex


def suggestion_created(suggestion: Suggestion, at: datetime, actor: str) -> AuditEvent:
    return AuditEvent(
        id=f"created:{suggestion.id}",  # fixed id: loading the same file twice writes once
        at=at,
        type="suggestion_created",
        suggestion_id=suggestion.id,
        actor=actor,
        data={
            "kind": suggestion.payload.kind,
            "store_id": suggestion.store_id,
            "model_version": suggestion.model_version,
            "data_snapshot_id": suggestion.data_snapshot_id,
            "config_digest": suggestion.config_digest,
        },
    )


def decision(suggestion: Suggestion, approval: Approval) -> AuditEvent:
    data: dict[str, str | float | int | bool | None] = {
        "actor_role": approval.actor_role,
        "from_state": suggestion.state,
    }
    if approval.edited_units is not None:
        data["edited_units"] = approval.edited_units
    if approval.reason:
        data["reason"] = approval.reason
    return AuditEvent(
        id=f"decision:{suggestion.id}",
        at=approval.at,
        type=_ACTION_EVENT[approval.action],
        suggestion_id=suggestion.id,
        actor=approval.actor_id,
        data=data,
    )


def expired(suggestion: Suggestion, at: datetime) -> AuditEvent:
    return AuditEvent(
        id=f"expired:{suggestion.id}",
        at=at,
        type="expired",
        suggestion_id=suggestion.id,
        actor="system",
        data={"deadline": suggestion.deadline.isoformat()},
    )


def superseded(suggestion: Suggestion, at: datetime) -> AuditEvent:
    """A newer run replaced this proposal before anyone decided it."""
    return AuditEvent(
        id=f"expired:{suggestion.id}",
        at=at,
        type="expired",
        suggestion_id=suggestion.id,
        actor="system",
        data={"reason": "superseded by a newer run"},
    )


def kill_switch(on: bool, actor: str, at: datetime) -> AuditEvent:
    return AuditEvent(id=_new_id(), at=at, type="kill_switch", actor=actor, data={"on": on})


def outcome(record: OutcomeRecord) -> AuditEvent:
    """One event per submission, so a correction leaves the first entry in the history."""
    return AuditEvent(
        id=_new_id(),
        at=record.recorded_at,
        type="outcome",
        suggestion_id=record.suggestion_id,
        actor=record.recorded_by,
        data={
            "kind": record.kind,
            "on": record.on.isoformat(),
            "store_id": record.store_id,
            "sku_id": record.sku_id,
            "units_sold": record.units_sold,
            "units_wasted": record.units_wasted,
            "sold_out": record.sold_out,
            "units_bought": record.units_bought,
            "source": record.source,
        },
    )
