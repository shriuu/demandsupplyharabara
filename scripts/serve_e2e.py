"""Run the REAL API with in-memory storage and a small synthetic fixture, for browser tests.

No network, no cloud. The sign-in values below are throwaway test values for this local
server only. Serves the built web app (``npm run build`` in frontend/pwa) on 127.0.0.1.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn

from harabhara.api.app import create_app
from harabhara.api.ports import FakeAssistant, FakePrices
from harabhara.api.settings import ApiSettings, User
from harabhara.api.storage import InMemoryStorage
from harabhara.contracts import Driver, OrderPayload, PriceQuote, Range, Suggestion

PORT = 8765
TEST_PINS = {
    "1111": User("e2e-store", "store_manager", "S1"),
    "3333": User("e2e-area", "area_manager"),
}
DIST = Path(__file__).resolve().parents[1] / "frontend/pwa/dist"


def _order(sid: str, sku: str, units: float, now: datetime, hours: int) -> Suggestion:
    return Suggestion(
        id=sid,
        store_id="S1",
        sku_id=sku,
        created_at=now - timedelta(hours=1),
        deadline=now + timedelta(hours=hours),
        approver_role="store_manager",
        reason="Rain is coming, so fewer shoppers will visit.",
        drivers=[Driver(kind="weather", direction="down", code="heavy_rain_walk_in")],
        payload=OrderPayload(
            recommended_units=units, range=Range(low=units - 2, likely=units, high=units + 3)
        ),
        model_version="e2e",
        data_snapshot_id="e2e-snapshot",
        config_digest="e2e-config",
    )


def build() -> uvicorn.Config:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    storage = InMemoryStorage()
    storage.create_suggestion(_order("e2e-tomato", "tomato", 8, now, 5))
    storage.create_suggestion(_order("e2e-banana", "banana", 20, now, 6))
    quote = PriceQuote(
        sku_id="tomato",
        market="Synthetic Mandi",
        on=now.date(),
        modal_inr=28,
        source="synthetic e2e feed",
        fetched_at=now,
        status="ok",
    )
    settings = ApiSettings(signing_key="e2e-only-signing-key", pins=TEST_PINS, static_dir=DIST)
    app = create_app(storage, settings, prices=FakePrices([quote]), assistant=FakeAssistant())
    return uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    uvicorn.Server(build()).run()
