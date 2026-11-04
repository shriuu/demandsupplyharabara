"""Turn forecasts, stock and the decision rules into suggestions (CLAUDE.md s9 steps 3 to 5).

Evening: one order suggestion per store and product. Morning: for one product across stores,
transfers first (they save sales at both ends), then markdowns for what is still expected to
expire, then surplus offers for what a markdown will not sell. Every suggestion carries the real
drivers behind it and a one-sentence reason from those drivers. The caller passes each
(suggestion, facts) pair through the rules engine; nothing here is shown to a person unchecked.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from harabhara.contracts import (
    Driver,
    MarkdownPayload,
    OrderPayload,
    Payload,
    Range,
    Suggestion,
    SurplusPayload,
    TransferPayload,
)
from harabhara.decisions.discount import plan_markdown
from harabhara.decisions.economics import critical_ratio, leftover_cost, lost_sale_cost
from harabhara.decisions.order import order_ask
from harabhara.decisions.surplus import Buyer, plan_surplus
from harabhara.decisions.transfer import plan_transfers
from harabhara.reasons.writer import Names, NoReasonError, write_reason
from harabhara.rules.guardrails import Facts
from harabhara.settings.schema import AppConfig
from harabhara.state.projection import Lot, expected_value, project

SURPLUS_GRADE = "B"  # lot grades are not in the sales data; B is assumed and flagged in the docs


@dataclass(frozen=True)
class Series:
    """What is known about one store and product that does not change within the day."""

    store_id: str
    sku_id: str
    category: str
    product: str
    unit: str
    format: str  # "Store" or "Dark store"
    price: float
    unit_cost: float
    life_days: int
    festival_sensitive: bool


@dataclass(frozen=True)
class Provenance:
    model_version: str
    data_snapshot_id: str
    config_digest: str


# ---- helpers -------------------------------------------------------------------------------


def _at(day: date, clock: str, cfg: AppConfig) -> datetime:
    return datetime.combine(day, time.fromisoformat(clock), tzinfo=ZoneInfo(cfg.schedule.timezone))


def _suggest(
    *,
    kind_id: str,
    series: Series,
    payload: Payload,
    drivers: list[Driver],
    approver: str,
    deadline: datetime,
    now: datetime,
    names: Names,
    cfg: AppConfig,
    prov: Provenance,
) -> Suggestion | None:
    try:
        reason = write_reason(
            payload=payload,
            drivers=drivers,
            store_id=series.store_id,
            names=names,
            max_chars=cfg.rules.explanations.max_reason_chars,
        )
    except NoReasonError:
        return None  # guardrail 9: no reason, no suggestion
    return Suggestion.model_validate(
        {
            "id": kind_id,
            "store_id": series.store_id,
            "sku_id": series.sku_id,
            "created_at": now,
            "deadline": deadline,
            "approver_role": approver,
            "state": "proposed",
            "reason": reason,
            "drivers": drivers,
            "payload": payload,
            "model_version": prov.model_version,
            "data_snapshot_id": prov.data_snapshot_id,
            "config_digest": prov.config_digest,
        }
    )


def _driver(kind: str, direction: str, code: str) -> Driver:
    return Driver.model_validate({"kind": kind, "direction": direction, "code": code})


# ---- evening: orders -----------------------------------------------------------------------


@dataclass(frozen=True)
class OrderInputs:
    series: Series
    on: date  # the day the stock will be sold
    demand: Range
    stock: float  # sellable carry-over on the shelf tomorrow
    manager_units: float | None  # what the managers' own rule would order, for comparison
    thin_history: bool
    weekend: bool
    heavy_rain: bool
    festival_eve_intensity: float
    hot_day: bool
    sold_out_at_origin: bool
    last_day_stock: float  # units that will be on their last sellable day tomorrow


def order_drivers(i: OrderInputs, cfg: AppConfig) -> list[Driver]:
    """The real causes behind an order, most important first."""
    d = cfg.modeling.decisions
    found: list[Driver] = []
    if i.thin_history:
        found.append(_driver("rule", "none", "thin_history"))
    if i.sold_out_at_origin:
        found.append(_driver("recent_sellout", "up", "sold_out_yesterday"))
    if i.festival_eve_intensity >= d.major_festival_intensity:
        if i.series.festival_sensitive:
            found.append(_driver("festival", "up", "festival_eve"))
        else:
            found.append(_driver("festival", "none", "festival_eve_flat"))
    if i.heavy_rain:
        if i.series.format == "Dark store":
            found.append(_driver("weather", "up", "heavy_rain_dark"))
        else:
            found.append(_driver("weather", "down", "heavy_rain_walk_in"))
    if i.weekend:
        found.append(_driver("weekday", "up", "weekend"))
    if i.hot_day and i.series.sku_id in d.heat_sensitive_skus:
        found.append(_driver("weather", "up", "hot_day"))
    if i.series.life_days == 2:
        found.append(_driver("shelf_life", "down", "two_day_life"))
    if i.last_day_stock > 0:
        found.append(_driver("stock_age", "down", "old_stock_lingers"))
    return found or [_driver("weekday", "none", "normal_day")]


def build_order(
    i: OrderInputs, *, cfg: AppConfig, names: Names, prov: Provenance, now: datetime
) -> tuple[Suggestion, Facts] | None:
    """The evening order for one store and product, with its range, reason and facts."""
    s, dp = i.series, cfg.modeling.decisions
    sale = lost_sale_cost(s.price, s.unit_cost, cfg.costs.basket_allowance_per_lost_sale_inr)
    left = leftover_cost(s.unit_cost, s.life_days, dp.waste_weight_exponent)
    ratio = max(critical_ratio(sale, left), dp.service_level_floor)
    ask = order_ask(i.demand, i.stock, ratio, cfg.modeling.demand.quantiles)
    recommended = float(round(ask))
    low = min(max(0.0, i.demand.likely - i.stock), recommended)
    high = max(recommended, i.demand.high - i.stock)
    payload = OrderPayload(
        recommended_units=recommended,
        range=Range(low=low, likely=recommended, high=high),
        manager_rule_units=i.manager_units,
    )
    drivers = order_drivers(i, cfg)
    end = cfg.schedule.evening_order_window.end
    suggestion = _suggest(
        kind_id=f"order:{s.store_id}:{s.sku_id}:{i.on}",
        series=s,
        payload=payload,
        drivers=drivers,
        approver="store_manager",
        deadline=_at(i.on - timedelta(days=1), end, cfg),
        now=now,
        names=names,
        cfg=cfg,
        prov=prov,
    )
    if suggestion is None:
        return None
    facts = Facts(
        category=s.category, price=s.price, unit_cost=s.unit_cost, thin_history=i.thin_history
    )
    return suggestion, facts


# ---- morning: transfers, markdowns, surplus ------------------------------------------------


@dataclass(frozen=True)
class MorningStore:
    series: Series
    lots: tuple[Lot, ...]  # on the shelf after today's delivery
    demand: tuple[Range, Range, Range]  # today, tomorrow, the day after
    delivered_today: float
    thin_history: bool
    opening: str  # "HH:MM"


def _units_with_life(lots: Sequence[Lot], life: int) -> float:
    return sum(lot.units for lot in lots if lot.life_left == life)


def build_morning(
    stores: Sequence[MorningStore],
    *,
    as_of: date,
    now: datetime,
    pairs: Set[tuple[str, str]],
    buyers: Sequence[Buyer],
    used_capacity: Mapping[str, float],
    names: Names,
    cfg: AppConfig,
    prov: Provenance,
) -> list[tuple[Suggestion, Facts]]:
    """Morning suggestions for one product across stores: transfers, markdowns, surplus."""
    if not stores:
        return []
    dp, rules = cfg.modeling.decisions, cfg.rules
    sample = stores[0].series
    now_hour = now.hour + now.minute / 60

    unsold: dict[str, float] = {}
    short: dict[str, float] = {}
    second_day: dict[str, float] = {}
    for st in stores:
        projection = project(
            store_id=st.series.store_id,
            sku_id=st.series.sku_id,
            as_of=as_of - timedelta(days=1),
            opening=st.lots,
            deliveries=[None, None, None],
            demand=list(st.demand),
            sales_order=cfg.modeling.projection.sales_order,
            assumptions=[],
            model_version=prov.model_version,
            data_snapshot_id=prov.data_snapshot_id,
            config_digest=prov.config_digest,
        )
        today, tomorrow = projection.days[0], projection.days[1]
        unsold[st.series.store_id] = expected_value(today.expected_waste)
        short[st.series.store_id] = expected_value(today.lost_sales)
        second_day[st.series.store_id] = expected_value(tomorrow.expected_waste)

    out: list[tuple[Suggestion, Facts]] = []
    by_id = {st.series.store_id: st for st in stores}

    surplus_map = {k: v for k, v in unsold.items() if v >= dp.alert_min_units}
    shortage_map = {k: v for k, v in short.items() if v >= dp.alert_min_units}
    transfers = plan_transfers(
        category=sample.category,
        now_hour=now_hour,
        surplus=surplus_map,
        shortage=shortage_map,
        pairs=pairs,
        price={st.series.store_id: st.series.price for st in stores},
        markdown_share=1 - rules.markdown.step_1_pct / 100,
        rules=rules.transfer,
        trip_minutes=dp.transfer_trip_minutes,
    )
    moved_out: dict[str, float] = {}
    for t in transfers:
        donor = by_id[t.from_store]
        moved_out[t.from_store] = moved_out.get(t.from_store, 0.0) + t.units
        suggestion = _suggest(
            kind_id=f"transfer:{t.from_store}:{t.to_store}:{sample.sku_id}:{as_of}",
            series=donor.series,
            payload=TransferPayload(
                from_store=t.from_store,
                to_store=t.to_store,
                units=t.units,
                leave_by=t.leave_by,
                van_cost_inr=t.van_cost_inr,
            ),
            drivers=[
                _driver("rule", "none", "surplus_expected"),
                _driver("rule", "up", "shortage_expected"),
                _driver("rule", "none", "van_pays"),
            ],
            approver=rules.transfer.approver,
            deadline=_at(as_of, f"{rules.transfer.approve_by_hour:02d}:00", cfg),
            now=now,
            names=names,
            cfg=cfg,
            prov=prov,
        )
        if suggestion is not None:
            lives = [lot.life_left for lot in donor.lots if lot.units > 0]
            facts = Facts(
                category=donor.series.category,
                life_left_days=min(lives) if lives else None,
                price=donor.series.price,
                unit_cost=donor.series.unit_cost,
                now_hour=now_hour,
                thin_history=donor.thin_history,
            )
            out.append((suggestion, facts))

    for st in stores:
        sid, series = st.series.store_id, st.series
        remaining = max(0.0, unsold[sid] - moved_out.get(sid, 0.0))
        last_day = _units_with_life(st.lots, 1)
        two_day = _units_with_life(st.lots, 2)
        proposals = plan_markdown(
            sku_id=series.sku_id,
            category=series.category,
            price=series.price,
            unit_cost=series.unit_cost,
            last_day_units=last_day if remaining >= dp.alert_min_units else 0.0,
            expected_unsold_last_day=remaining,
            second_day_units=two_day,
            expected_unsold_second_day=second_day[sid]
            if second_day[sid] >= dp.alert_min_units
            else 0.0,
            baseline_demand=st.demand[0].likely,
            opening=st.opening,
            rules=rules.markdown,
            lift=dp.markdown_demand_lift,
            earlier_min_share=dp.earlier_markdown_min_share,
        )
        for p in proposals:
            share = p.units / st.delivered_today if st.delivered_today > 0 else 0.0
            big = share > rules.markdown.area_manager_approval_if_share_of_days_delivery_above
            drivers = [
                _driver("rule", "none", "expires_soon")
                if p.earlier_than_last_day
                else _driver("shelf_life", "down", "last_day")
            ]
            if "below cost" in p.note:
                drivers.append(_driver("rule", "none", "below_cost_wait"))
            if st.thin_history:
                drivers.insert(0, _driver("rule", "none", "thin_history"))
            suggestion = _suggest(
                kind_id=(
                    f"markdown:{sid}:{series.sku_id}:{as_of}:{p.step_pct:g}:{p.start}"
                    f"{':early' if p.earlier_than_last_day else ''}"
                ),
                series=series,
                payload=MarkdownPayload(
                    units=p.units,
                    step_pct=p.step_pct,
                    start=p.start,
                    expected_recovery_inr=p.expected_recovery_inr,
                    earlier_than_last_day=p.earlier_than_last_day,
                ),
                drivers=drivers,
                approver="area_manager" if big else rules.markdown.approver_default,
                deadline=_at(as_of, st.opening, cfg),
                now=now,
                names=names,
                cfg=cfg,
                prov=prov,
            )
            if suggestion is not None:
                facts = Facts(
                    category=series.category,
                    life_left_days=2 if p.earlier_than_last_day else 1,
                    price=series.price,
                    unit_cost=series.unit_cost,
                    day_delivery_units=st.delivered_today,
                    now_hour=now_hour,
                    thin_history=st.thin_history,
                )
                out.append((suggestion, facts))

        sold_by_markdown = min(remaining, st.demand[0].likely * dp.markdown_demand_lift)
        leftover = remaining - sold_by_markdown
        if leftover >= dp.alert_min_units:
            used = dict(used_capacity)
            plan = plan_surplus(
                store_id=sid,
                sku_id=series.sku_id,
                grade=SURPLUS_GRADE,
                units=leftover,
                retail_price=series.price,
                now=now,
                buyers=buyers,
                used_capacity=used,
                horizon_hours=dp.surplus_horizon_hours,
            )
            buyer_by_id = {b.buyer_id: b for b in buyers}
            for match in plan.matches:
                suggestion = _suggest(
                    kind_id=f"surplus:{sid}:{series.sku_id}:{as_of}:{match.buyer_id}",
                    series=series,
                    payload=SurplusPayload(
                        buyer_id=match.buyer_id,
                        units=match.units,
                        grade=SURPLUS_GRADE,
                        pickup_window=match.window,
                        expected_recovery_inr=match.expected_recovery_inr,
                        price_share_of_retail=match.price_share,
                        profit_vs_cost_inr=match.expected_recovery_inr
                        - match.units * series.unit_cost,
                    ),
                    drivers=[
                        _driver("rule", "none", "surplus_expected"),
                        _driver("rule", "none", "buyer_fits"),
                    ],
                    approver="store_manager",
                    deadline=_at(as_of, cfg.schedule.surplus_plan_confirm_by, cfg),
                    now=now,
                    names=names,
                    cfg=cfg,
                    prov=prov,
                )
                if suggestion is not None:
                    facts = Facts(
                        category=series.category,
                        price=series.price,
                        unit_cost=series.unit_cost,
                        buyer=buyer_by_id[match.buyer_id],
                        thin_history=st.thin_history,
                    )
                    out.append((suggestion, facts))
    return out
