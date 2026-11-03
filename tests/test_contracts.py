from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from harabhara.contracts import (
    Approval,
    Driver,
    Forecast,
    MarkdownPayload,
    OrderPayload,
    PriceQuote,
    Range,
    Suggestion,
    TrimmingSuggestion,
)

NOW = datetime(2026, 11, 3, 21, 0, tzinfo=UTC)
RANGE = Range(low=8, likely=10, high=14)


def _suggestion(**over: object) -> Suggestion:
    base: dict[str, object] = {
        "id": "s1",
        "store_id": "S01",
        "sku_id": "P13",
        "created_at": NOW,
        "deadline": NOW,
        "approver_role": "store_manager",
        "reason": "Coriander lasts two days, so order close to what sells.",
        "drivers": [Driver(kind="shelf_life", direction="down", code="two_day_life")],
        "payload": OrderPayload(recommended_units=10, range=RANGE),
        "model_version": "m1",
        "data_snapshot_id": "d1",
        "config_digest": "c1",
    }
    return Suggestion.model_validate(base | over)


def test_range_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        Range(low=5, likely=3, high=9)


def test_forecast_horizon_is_one_to_three_days() -> None:
    kwargs = {
        "store_id": "S01",
        "sku_id": "P01",
        "target_date": date(2026, 11, 4),
        "demand": RANGE,
        "model_version": "m",
        "data_snapshot_id": "d",
        "config_digest": "c",
    }
    Forecast(horizon_days=3, **kwargs)
    with pytest.raises(ValidationError):
        Forecast(horizon_days=4, **kwargs)


def test_suggestion_needs_a_reason_and_a_driver() -> None:
    with pytest.raises(ValidationError):
        _suggestion(reason="")
    with pytest.raises(ValidationError):
        _suggestion(drivers=[])


def test_payload_kind_selects_the_right_shape() -> None:
    adapter = TypeAdapter(Suggestion)
    raw = _suggestion().model_dump(mode="json")
    assert isinstance(adapter.validate_python(raw).payload, OrderPayload)
    raw["payload"] = {
        "kind": "markdown",
        "units": 5,
        "step_pct": 30,
        "start": "09:00",
        "expected_recovery_inr": 120,
    }
    assert isinstance(adapter.validate_python(raw).payload, MarkdownPayload)
    raw["payload"] = {"kind": "order", "units": 5}
    with pytest.raises(ValidationError):
        adapter.validate_python(raw)


def test_an_edit_needs_units_and_a_reason() -> None:
    common = {
        "suggestion_id": "s1",
        "actor_role": "store_manager",
        "actor_id": "u1",
        "at": NOW,
    }
    with pytest.raises(ValidationError):
        Approval(action="edit", edited_units=8, **common)
    with pytest.raises(ValidationError):
        Approval(action="edit", reason="rain", **common)
    assert Approval(action="edit", edited_units=8, reason="rain", **common).edited_units == 8
    assert Approval(action="approve", **common).reason is None


def test_a_price_is_never_invented() -> None:
    kwargs = {
        "sku_id": "P01",
        "market": "Bengaluru",
        "on": date(2026, 11, 3),
        "source": "data.gov.in (Agmarknet)",
        "fetched_at": NOW,
    }
    with pytest.raises(ValidationError):
        PriceQuote(status="unavailable", modal_inr=20.0, **kwargs)
    with pytest.raises(ValidationError):
        PriceQuote(status="ok", **kwargs)
    assert PriceQuote(status="unavailable", **kwargs).modal_inr is None
    with pytest.raises(ValidationError):
        PriceQuote(status="ok", modal_inr=20.0, **{**kwargs, "source": ""})


def test_trimming_suggestion_needs_a_reason_and_no_negative_units() -> None:
    ok = TrimmingSuggestion(
        on=date(2026, 11, 4), sku_id="P13", spot_units_to_trim=0, reason="Stock is long."
    )
    assert ok.spot_units_to_trim == 0
    with pytest.raises(ValidationError):
        TrimmingSuggestion(on=date(2026, 11, 4), sku_id="P13", spot_units_to_trim=-1, reason="x")
    with pytest.raises(ValidationError):
        TrimmingSuggestion(on=date(2026, 11, 4), sku_id="P13", spot_units_to_trim=1, reason="")
