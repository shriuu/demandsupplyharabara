"""Typed schemas for the files in ``config/``.

Every limit the code uses lives in YAML and is validated here. Unknown keys are rejected so a
typo cannot silently turn a rule off. A value that the playbook does not give is ``None`` (an
open owner question), never a guess; see ``harabhara.settings.loader.require``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

Hour = Field(ge=0, le=24)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---- rules.yaml -----------------------------------------------------------------------------


class Grading(_Strict):
    A: dict[str, Any]
    B: dict[str, Any]
    C: dict[str, Any]
    full_price_grades: list[str]
    note: str


class Receiving(_Strict):
    hot_arrival_temp_c: float
    hot_arrival_life_penalty_days: int = Field(ge=0)
    no_cold_room_skus_source: str
    chilling_injury_below_c: float
    leafy_greens_max_crate_stack: int = Field(ge=1)


class ShelfLife(_Strict):
    rules_table: str
    count_starts: str
    model_may_exceed_rule: bool


class Markdown(_Strict):
    step_1_pct: float = Field(gt=0, lt=100)
    step_1_when: str
    step_2_pct: float = Field(gt=0, lt=100)
    step_2_after_hour: int = Hour
    step_2_categories_or_skus: list[str]
    floor_basis_before_step_2: str
    approver_default: str
    area_manager_approval_if_share_of_days_delivery_above: float = Field(ge=0, le=1)
    earlier_start_allowed: bool | None
    promo_pct_in_data: float = Field(ge=0, lt=100)


class Transfer(_Strict):
    max_distance_km: float = Field(gt=0)
    must_arrive_before_hour: int = Hour
    van_cost_inr: float = Field(ge=0)
    min_units_low_value: int = Field(ge=0)
    low_value_threshold_inr: float | None
    leafy_greens_no_transfer_after_hour: int = Hour
    approver: str
    approve_by_hour: int = Hour
    store_distances: dict[str, dict[str, float]] | None


class Surplus(_Strict):
    channel_order: list[str]
    landfill_edible_allowed: bool
    notice_hours_source: str
    store_confirms_plan_by_hour: int = Hour
    grade_c_channels: list[str]


class Farmers(_Strict):
    floor_prices_source: str
    never_below_floor: bool
    never_cancel_confirmed_volume: bool
    payment_terms_days: int = Field(ge=0)
    trim_order_when_long: list[str]
    share_forecast_horizon_days: int = Field(ge=1)


class Ordering(_Strict):
    forecast_horizon_days: int = Field(ge=1)
    approval_required: bool
    big_edit_reason_threshold: float | None


class Automation(_Strict):
    auto_order_allowed: bool
    pilot_weeks_before_auto: int = Field(ge=0)


class ManagersRuleBaseline(_Strict):
    avg_window_days: int = Field(ge=1)
    weekend_bump_pct: float
    festival_bump_pct: float
    extra_buffer_pct: float | None


class Rules(_Strict):
    version: str
    playbook_version: str
    grading: Grading
    receiving: Receiving
    shelf_life: ShelfLife
    markdown: Markdown
    transfer: Transfer
    surplus: Surplus
    farmers: Farmers
    ordering: Ordering
    automation: Automation
    managers_rule_baseline: ManagersRuleBaseline


# ---- schedule.yaml --------------------------------------------------------------------------

Clock = Field(pattern=r"^([01]\d|2[0-3]|24):[0-5]\d$")


class Window(_Strict):
    start: str = Clock
    end: str = Clock


class OpeningHours(_Strict):
    open: str = Clock
    close: str = Clock


class StoreHours(_Strict):
    Store: OpeningHours
    Dark_store: OpeningHours = Field(alias="Dark store")


class Schedule(_Strict):
    version: str
    timezone: str
    evening_order_window: Window
    dc_order_total_and_fpo_booking: str = Clock
    mandi_purchase_window: Window
    dispatch_by: str = Clock
    store_delivery_by: str = Clock
    transfer_approval_by: str = Clock
    transfer_van_cutoff: str = Clock
    leafy_greens_transfer_cutoff: str = Clock
    surplus_plan_confirm_by: str = Clock
    markdown_step2_from: str = Clock
    store_hours: StoreHours
    closing_record: str | None
    order_deadline_missed: str | None


# ---- metrics.yaml ---------------------------------------------------------------------------


class Holdout(_Strict):
    start: date
    end: date
    days: int = Field(ge=1)


class Metrics(_Strict):
    version: str
    evaluation_rows: str
    exclude_rows: list[str]
    wastage_rate: str
    stockout_rate: str
    sell_through: str
    wape: str
    bias: str
    gross_margin: str
    shelf_life_mae: str
    manager_acceptance: str
    farmer_share: str | None
    baseline: dict[str, float]
    targets: dict[str, float | str]
    holdout: Holdout


# ---- costs.yaml -----------------------------------------------------------------------------


class Costs(_Strict):
    version: str
    unit_cost_source: str
    waste_cost: str
    lost_sale_margin_source: str
    basket_allowance_per_lost_sale_inr: float | None
    basket_allowance_skus_hint: list[str]
    waste_definition_includes: str | None
    cost_ratio_per_sku: str


# ---- feeds.yaml -----------------------------------------------------------------------------


class PriceShock(_Strict):
    lookback_days: int = Field(ge=1)
    ratio_threshold: float = Field(gt=1)


class Mandi(_Strict):
    provider: str
    base_url: str
    resource_id: str
    citation: str = Field(min_length=1)
    state: str
    district: str
    markets: list[str] = Field(min_length=1)
    user_agent: str
    timeout_s: float = Field(gt=0)
    page_limit: int = Field(ge=1, le=1000)
    kg_per_quintal: float = Field(gt=0)
    cache_ttl_hours: float = Field(ge=0)
    stale_after_hours: float = Field(gt=0)
    drop_after_hours: float = Field(gt=0)
    history_keep_days: int = Field(ge=1)
    price_max_age_days: int = Field(ge=0)
    products: dict[str, str]
    unverified_unit_products: list[str]
    price_shock: PriceShock


class AssistantSettings(_Strict):
    provider: str
    model: str = Field(min_length=1)
    base_url: str
    timeout_s: float = Field(gt=0)
    max_output_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0, le=2)
    max_question_chars: int = Field(ge=1)
    max_answer_chars: int = Field(ge=1)
    rate_limit_calls: int = Field(ge=1)
    rate_limit_window_s: float = Field(gt=0)
    dont_have_answer: str = Field(min_length=1)
    failure_message: str = Field(min_length=1)


class Feeds(_Strict):
    version: str
    mandi: Mandi
    assistant: AssistantSettings


# ---- whole config ---------------------------------------------------------------------------


class AppConfig(_Strict):
    rules: Rules
    schedule: Schedule
    metrics: Metrics
    costs: Costs
    feeds: Feeds
    digest: str = Field(description="SHA-256 over the config files; pinned on every run")
