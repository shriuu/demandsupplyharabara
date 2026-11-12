"""Shared data contracts: what the models, decision layer, API and screens exchange.

Every workstream builds against these types. Changing one needs a pull request that updates
``docs/api.md`` and the tests in ``tests/test_contracts.py``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["store_manager", "area_manager", "dc_lead", "farmer_coordinator"]
Clock = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]|24):[0-5]\d$")]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Range(_Frozen):
    """A forecast is always a range; screens may show ``likely`` only."""

    low: float = Field(ge=0)
    likely: float = Field(ge=0)
    high: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Range:
        if not self.low <= self.likely <= self.high:
            msg = "range must satisfy low <= likely <= high"
            raise ValueError(msg)
        return self


ThinHistoryFlag = Literal[
    "new_season", "new_store", "new_product", "missing_weather", "missing_price"
]


class Forecast(_Frozen):
    store_id: str
    sku_id: str
    target_date: date
    horizon_days: int = Field(ge=1, le=3)
    demand: Range
    flags: list[ThinHistoryFlag] = Field(default_factory=list)
    demand_estimated: bool = Field(
        default=False, description="True when history behind this used sold-out corrections"
    )
    model_version: str
    data_snapshot_id: str
    config_digest: str


class Driver(_Frozen):
    """A real cause behind a suggestion. Reasons are built only from these."""

    kind: Literal[
        "weather",
        "weekday",
        "festival",
        "stock_age",
        "shelf_life",
        "recent_sellout",
        "price",
        "promotion",
        "rule",
    ]
    direction: Literal["up", "down", "none"]
    code: str = Field(min_length=1, description="machine key, e.g. heavy_rain_walk_in")
    detail: str = Field(default="", description="short human fact, e.g. '2 sellable days'")


# ---- suggestion payloads (one per kind) ----------------------------------------------------


class OrderPayload(_Frozen):
    kind: Literal["order"] = "order"
    recommended_units: float = Field(ge=0)
    range: Range
    manager_rule_units: float | None = Field(default=None, ge=0)


class MarkdownPayload(_Frozen):
    kind: Literal["markdown"] = "markdown"
    units: float = Field(gt=0)
    step_pct: float = Field(gt=0, lt=100)
    start: Clock
    expected_recovery_inr: float = Field(ge=0)
    earlier_than_last_day: bool = False


class TransferPayload(_Frozen):
    kind: Literal["transfer"] = "transfer"
    from_store: str
    to_store: str
    units: float = Field(gt=0)
    leave_by: Clock
    van_cost_inr: float = Field(ge=0)


class SurplusPayload(_Frozen):
    kind: Literal["surplus"] = "surplus"
    buyer_id: str
    units: float = Field(gt=0)
    grade: Literal["A", "B", "C"]
    pickup_window: str
    pickup_date: date | None = None  # the day of that window, so "06:00-08:00" is never ambiguous
    expected_recovery_inr: float = Field(ge=0)
    # What the buyer pays as a share of the shelf price, and the result against purchase cost
    # (negative = below cost, still better than binning). None when not known.
    buyer_name: str | None = None
    price_share_of_retail: float | None = Field(default=None, ge=0, le=1)
    profit_vs_cost_inr: float | None = None


Payload = Annotated[
    OrderPayload | MarkdownPayload | TransferPayload | SurplusPayload,
    Field(discriminator="kind"),
]

SuggestionState = Literal["proposed", "approved", "edited", "rejected", "expired", "done"]


class Suggestion(_Frozen):
    id: str
    store_id: str
    sku_id: str
    created_at: datetime
    deadline: datetime
    approver_role: Role
    state: SuggestionState = "proposed"
    reason: str = Field(min_length=1, description="one sentence a manager would say (guardrail 9)")
    drivers: list[Driver] = Field(min_length=1)
    payload: Payload
    model_version: str
    data_snapshot_id: str
    config_digest: str


class Approval(_Frozen):
    suggestion_id: str
    action: Literal["approve", "edit", "reject"]
    actor_role: Role
    actor_id: str
    at: datetime
    edited_units: float | None = Field(default=None, ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def _edit_needs_reason(self) -> Approval:
        if self.action == "edit" and (self.edited_units is None or not self.reason):
            msg = "an edit needs edited_units and a reason (guardrail 1)"
            raise ValueError(msg)
        return self


class AuditEvent(_Frozen):
    """Append-only. Never updated or deleted."""

    id: str
    at: datetime
    type: Literal[
        "suggestion_created", "approved", "edited", "rejected", "expired", "outcome", "kill_switch"
    ]
    suggestion_id: str | None = None
    actor: str
    data: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


# ---- other views ---------------------------------------------------------------------------


class PriceQuote(_Frozen):
    """A public mandi price. Never invented: unavailable means no price (guardrails 11, 12)."""

    sku_id: str
    market: str
    on: date
    modal_inr: float | None = Field(default=None, ge=0)
    min_inr: float | None = Field(default=None, ge=0)
    max_inr: float | None = Field(default=None, ge=0)
    source: str = Field(min_length=1, description="citation shown next to the price")
    fetched_at: datetime
    status: Literal["ok", "stale", "unavailable"]

    @model_validator(mode="after")
    def _no_price_when_unavailable(self) -> PriceQuote:
        if self.status == "unavailable" and self.modal_inr is not None:
            msg = "an unavailable quote must not carry a price"
            raise ValueError(msg)
        if self.status != "unavailable" and self.modal_inr is None:
            msg = "an ok or stale quote needs a modal price"
            raise ValueError(msg)
        return self


class FarmerVolumeForecast(_Frozen):
    fpo_id: str
    sku_id: str
    on: date
    volume: Range
    label: Literal["estimate"] = "estimate"  # information only, never a commitment


class TrimmingSuggestion(_Frozen):
    """Advice to the DC buying lead: trim this much spot (mandi) buying first.

    Spot buying only. Confirmed farmer-group volume is never part of it (guardrail 3).
    """

    on: date
    sku_id: str
    spot_units_to_trim: float = Field(ge=0)
    reason: str = Field(min_length=1)


class Scorecard(_Frozen):
    """Waste, empty shelves and farmer share travel together (guardrail 4)."""

    scope: str
    period_start: date
    period_end: date
    waste_pct: float
    stockout_pct: float
    farmer_share: float | None
    farmer_share_definition: str | None = None

    @model_validator(mode="after")
    def _farmer_share_is_explained(self) -> Scorecard:
        if self.farmer_share is None and not self.farmer_share_definition:
            msg = "an unknown farmer share must say why it is unknown"
            raise ValueError(msg)
        return self


# ---- what really happened ------------------------------------------------------------------


class OutcomeRecord(_Frozen):
    """Entered by a person after the fact: a store's closing counts, or what the DC bought."""

    kind: Literal["closing", "purchase"]
    on: date
    store_id: str | None = None
    sku_id: str
    units_sold: float | None = Field(default=None, ge=0)
    units_wasted: float | None = Field(default=None, ge=0)
    sold_out: bool | None = None
    # Stock still on the shelf when the store closed (not thrown away). Optional: older records and
    # stores that do not count it leave it blank, and a blank is never read as zero.
    units_left: float | None = Field(default=None, ge=0)
    units_bought: float | None = Field(default=None, ge=0)
    source: Literal["farmer_group", "spot"] | None = None
    market: str | None = Field(
        default=None, max_length=60, description="the mandi, for spot buying"
    )
    suggestion_id: str | None = None
    recorded_by: str
    recorded_at: datetime

    @model_validator(mode="after")
    def _fits_its_kind(self) -> OutcomeRecord:
        closing = (self.units_sold, self.units_wasted, self.sold_out)
        buying = (self.units_bought, self.source)
        if self.kind == "closing":
            ok = self.store_id and None not in closing and all(v is None for v in buying)
            msg = "a closing record needs a store, sold, wasted, sold-out and nothing about buying"
        else:
            ok = (
                self.store_id is None
                and None not in buying
                and all(v is None for v in (*closing, self.units_left))
            )
            msg = "a purchase record needs units bought and a source, and nothing about a store"
        if (
            ok
            and self.market is not None
            and not (self.kind == "purchase" and self.source == "spot")
        ):
            ok = False
            msg = "a market belongs only to spot buying"
        if not ok:
            raise ValueError(msg)
        return self


# ---- three-day projection ------------------------------------------------------------------


class ProjectionDay(_Frozen):
    """One day of the stock roll-forward. Every figure is a range over low/likely/high demand."""

    day: int = Field(ge=1, le=3)
    on: date
    demand: Range
    sold: Range
    lost_sales: Range
    expected_waste: Range
    closing_stock: Range


class Projection(_Frozen):
    """Where stock, shelf life and demand lead over the next three days for one store-product."""

    store_id: str
    sku_id: str
    as_of: date
    days: list[ProjectionDay] = Field(min_length=1, max_length=3)
    assumptions: list[str] = Field(
        default_factory=list, description="e.g. 'lot ages inferred first-in first-out'"
    )
    model_version: str
    data_snapshot_id: str
    config_digest: str
