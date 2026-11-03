"""Shared fixtures. Everything is synthetic and in memory: no network, no data files."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harabhara.api.app import create_app
from harabhara.api.ports import FakeAssistant, FakePrices
from harabhara.api.settings import ApiSettings, User
from harabhara.api.storage import InMemoryStorage
from harabhara.contracts import (
    Driver,
    FarmerVolumeForecast,
    Forecast,
    MarkdownPayload,
    OrderPayload,
    PriceQuote,
    Range,
    Role,
    Scorecard,
    Suggestion,
    TransferPayload,
)

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 11, 10, 20, 45, tzinfo=IST)  # inside the evening ordering window
TODAY = NOW.date()

PINS = {
    "1111": User("mgr-s1", "store_manager", "S1"),
    "2222": User("mgr-s2", "store_manager", "S2"),
    "3333": User("area-1", "area_manager"),
    "4444": User("dc-1", "dc_lead"),
    "5555": User("farm-1", "farmer_coordinator"),
}


class Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: float) -> None:
        self.now += timedelta(**kw)


def make_suggestion(
    sid: str = "sg-1",
    store: str = "S1",
    approver: Role = "store_manager",
    deadline: datetime | None = None,
    payload: OrderPayload | MarkdownPayload | TransferPayload | None = None,
) -> Suggestion:
    return Suggestion(
        id=sid,
        store_id=store,
        sku_id="tomato",
        created_at=NOW - timedelta(hours=1),
        deadline=deadline or NOW + timedelta(hours=1),
        approver_role=approver,
        reason="Rain is coming, so fewer shoppers will visit.",
        drivers=[Driver(kind="weather", direction="down", code="heavy_rain_walk_in")],
        payload=payload
        or OrderPayload(recommended_units=40, range=Range(low=30, likely=40, high=55)),
        model_version="m-test",
        data_snapshot_id="snap-test",
        config_digest="cfg-test",
    )


def make_forecast(store: str = "S1", sku: str = "tomato", on: date = TODAY) -> Forecast:
    return Forecast(
        store_id=store,
        sku_id=sku,
        target_date=on,
        horizon_days=1,
        demand=Range(low=20, likely=30, high=45),
        model_version="m-test",
        data_snapshot_id="snap-test",
        config_digest="cfg-test",
    )


def make_quote(status: str = "ok") -> PriceQuote:
    return PriceQuote.model_validate(
        {
            "sku_id": "tomato",
            "market": "Test Mandi",
            "on": TODAY,
            "modal_inr": None if status == "unavailable" else 2400.0,
            "source": "synthetic test feed",
            "fetched_at": NOW,
            "status": status,
        }
    )


@dataclass
class Env:
    storage: InMemoryStorage
    clock: Clock
    prices: FakePrices
    assistant: FakeAssistant
    client: TestClient
    app: FastAPI
    login: Callable[[str], dict[str, str]]


@pytest.fixture
def env() -> Env:
    storage = InMemoryStorage()
    clock = Clock()
    prices = FakePrices([make_quote()])
    assistant = FakeAssistant()
    settings = ApiSettings(signing_key="test-signing-key", pins=PINS)
    app = create_app(storage, settings, prices=prices, assistant=assistant, clock=clock)
    client = TestClient(app)

    def login(pin: str) -> dict[str, str]:
        r = client.post("/api/v1/auth/login", json={"pin": pin})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

    return Env(storage, clock, prices, assistant, client, app, login)


def decision_body(sid: str, action: str, role: str, **extra: Any) -> dict[str, Any]:
    return {
        "suggestion_id": sid,
        "action": action,
        "actor_role": role,
        "actor_id": "x",
        "at": NOW.isoformat(),
        **extra,
    }


def farmer_row() -> FarmerVolumeForecast:
    return FarmerVolumeForecast(
        fpo_id="fpo-1", sku_id="tomato", on=TODAY, volume=Range(low=1, likely=2, high=3)
    )


def scorecard_row() -> Scorecard:
    return Scorecard(
        scope="S1",
        period_start=TODAY - timedelta(days=7),
        period_end=TODAY,
        waste_pct=4.0,
        stockout_pct=2.0,
        farmer_share=0.4,
        farmer_share_definition="synthetic test definition",
    )
