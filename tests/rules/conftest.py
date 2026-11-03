from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from harabhara.contracts import (
    Driver,
    MarkdownPayload,
    OrderPayload,
    Range,
    Suggestion,
    SurplusPayload,
    TransferPayload,
)
from harabhara.rules.engine import RulesEngine
from harabhara.rules.guardrails import Facts
from harabhara.settings import AppConfig, load_config

IST = timezone(timedelta(hours=5, minutes=30))
MORNING = datetime(2026, 11, 4, 8, 30, tzinfo=IST)


@pytest.fixture(scope="session")
def cfg() -> AppConfig:
    return load_config()


@pytest.fixture(scope="session")
def engine(cfg: AppConfig) -> RulesEngine:
    return RulesEngine(cfg)


def suggestion(payload: Any, **over: Any) -> Suggestion:
    base: dict[str, Any] = {
        "id": "s1",
        "store_id": "S01",
        "sku_id": "P01",
        "created_at": MORNING - timedelta(hours=1),
        "deadline": MORNING,
        "approver_role": "store_manager",
        "state": "proposed",
        "reason": "Tomatoes are on their last day, so mark them down from opening.",
        "drivers": [Driver(kind="shelf_life", direction="down", code="last_day")],
        "payload": payload,
        "model_version": "m",
        "data_snapshot_id": "d",
        "config_digest": "c",
    }
    return Suggestion.model_validate({**base, **over})


def markdown(**over: Any) -> MarkdownPayload:
    base: dict[str, Any] = {
        "units": 20.0,
        "step_pct": 30.0,
        "start": "07:00",
        "expected_recovery_inr": 100.0,
        "earlier_than_last_day": False,
    }
    return MarkdownPayload(**{**base, **over})


def transfer(**over: Any) -> TransferPayload:
    base: dict[str, Any] = {
        "from_store": "S01",
        "to_store": "S02",
        "units": 25.0,
        "leave_by": "09:30",
        "van_cost_inr": 300.0,
    }
    return TransferPayload(**{**base, **over})


def surplus(**over: Any) -> SurplusPayload:
    base: dict[str, Any] = {
        "buyer_id": "B1",
        "units": 30.0,
        "grade": "B",
        "pickup_window": "21:00-23:00",
        "expected_recovery_inr": 300.0,
    }
    return SurplusPayload(**{**base, **over})


def order() -> OrderPayload:
    return OrderPayload(recommended_units=40.0, range=Range(low=30, likely=40, high=55))


def good_facts(**over: Any) -> Facts:
    base: dict[str, Any] = {
        "category": "Vegetables",
        "life_left_days": 1,
        "price": 40.0,
        "unit_cost": 20.0,
        "now_hour": 7.5,
    }
    return Facts(**{**base, **over})
