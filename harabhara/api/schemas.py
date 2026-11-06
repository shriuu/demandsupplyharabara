"""Request and response bodies that are not shared contracts (see harabhara/contracts.py)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from harabhara.contracts import Range, Role, ThinHistoryFlag


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_Body):
    pin: str


class LoginResponse(_Body):
    token: str
    role: Role
    actor_id: str
    store_id: str | None
    area_id: str | None = None
    area_name: str | None = None


class KillSwitchRequest(_Body):
    on: bool


class KillSwitchResponse(_Body):
    status: str
    kill_switch: bool


class HealthResponse(_Body):
    status: str
    kill_switch: bool


class AskRequest(_Body):
    suggestion_id: str
    question: str


class AskResponse(_Body):
    suggestion_id: str
    answer: str
    # "assistant" when the assistant answered, "stored_reason" when it was unavailable
    source: str


class ProductTotal(_Body):
    sku_id: str
    demand: Range
    stores: int
    flags: list[ThinHistoryFlag]
    demand_estimated: bool
    model_version: str
    data_snapshot_id: str
    config_digest: str


class TrimmingHint(_Body):
    """Spot (mandi) buying is trimmed first; confirmed farmer volume is never touched (G03)."""

    sku_id: str
    spot_units_to_trim: float
    reason: str


class DcTotals(_Body):
    on: date
    totals: list[ProductTotal]
    trimming: list[TrimmingHint]
    stale: bool


class StoreOrder(_Body):
    """One store's order of one product: what the DC would send there."""

    store_id: str
    area_id: str | None
    area_name: str | None
    confirmed_units: float
    waiting_units: float
    rejected: bool


class ProductOrders(_Body):
    """What the stores have ordered of one product for the DC to buy."""

    sku_id: str
    confirmed_units: float  # approved, or edited to the manager's own amount
    waiting_units: float  # the suggested amount where nobody has decided yet
    stores_decided: int
    stores_waiting: int
    stores_rejected: int
    stores: list[StoreOrder]


class BoughtRow(_Body):
    sku_id: str
    source: Literal["farmer_group", "spot"]
    market: str | None
    units: float


class DcOrders(_Body):
    on: date | None
    products: list[ProductOrders]
    bought: list[BoughtRow]
    markets: list[str]
    all_decided: bool
    stale: bool


class OutcomeInput(_Body):
    """What a person enters. Who and when come from the sign-in and the server clock."""

    kind: Literal["closing", "purchase"]
    on: date
    store_id: str | None = None
    sku_id: str
    units_sold: float | None = Field(default=None, ge=0)
    units_wasted: float | None = Field(default=None, ge=0)
    sold_out: bool | None = None
    units_bought: float | None = Field(default=None, ge=0)
    source: Literal["farmer_group", "spot"] | None = None
    market: str | None = Field(default=None, max_length=60)
    suggestion_id: str | None = None
