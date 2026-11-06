"""The service behind the routes: role scoping, decisions, expiry, kill switch, fallbacks.

Nothing here orders, reprices or moves stock (guardrail 1). The only writes are the loader's
suggestions, a person's decision, the expiry of an overdue suggestion, and the kill switch.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import date, datetime, timedelta

from harabhara.api import ports
from harabhara.api.schemas import (
    AskResponse,
    BoughtRow,
    DcOrders,
    DcTotals,
    HealthResponse,
    KillSwitchResponse,
    OutcomeInput,
    ProductOrders,
    ProductTotal,
    TrimmingHint,
)
from harabhara.api.settings import User
from harabhara.api.storage import AlreadyExistsError, Storage
from harabhara.contracts import (
    Approval,
    AuditEvent,
    FarmerVolumeForecast,
    Forecast,
    OrderPayload,
    OutcomeRecord,
    PriceQuote,
    Projection,
    Range,
    Role,
    Scorecard,
    Suggestion,
    SuggestionState,
)
from harabhara.settings.areas import Area
from harabhara.settings.contacts import StoreContact
from harabhara.sim.recorded import scorecards_from_outcomes
from harabhara.workflow import audit, fallback
from harabhara.workflow.approvals import DecisionError, due_for_expiry, may_decide, next_state
from harabhara.workflow.deadlines import LOCAL_TZ, aware
from harabhara.workflow.fallback import Served


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


_DECISION_STATUS = {"not_proposed": 409, "overdue": 409, "mismatch": 422, "illegal": 409}


def _latest_per_scope(rows: list[Scorecard]) -> list[Scorecard]:
    """One scoreboard per store: each daily run adds a period, and only the newest is current."""
    newest: dict[str, Scorecard] = {}
    for row in rows:
        kept = newest.get(row.scope)
        if kept is None or row.period_end > kept.period_end:
            newest[row.scope] = row
    return sorted(newest.values(), key=lambda r: r.scope)


class Service:
    def __init__(
        self,
        storage: Storage,
        prices: ports.PricePort,
        assistant: ports.AssistantPort,
        clock: Callable[[], datetime] | None = None,
        scorecard_days: int = 28,
        contacts: list[StoreContact] | None = None,
        buying_markets: list[str] | None = None,
        areas: dict[str, Area] | None = None,
    ) -> None:
        self.storage = storage
        self._areas = areas or {}
        self._markets = buying_markets or []
        self._contacts = contacts or []
        self.scorecard_days = scorecard_days
        self.prices = prices
        self.assistant = assistant
        self._clock = clock or (lambda: datetime.now(LOCAL_TZ))

    def now(self) -> datetime:
        return aware(self._clock())

    # ---- scoping -------------------------------------------------------------------------

    @staticmethod
    def require_role(user: User, *roles: Role) -> None:
        if user.role not in roles:
            raise ApiError(403, "this role cannot use this endpoint")

    def _area_stores(self, user: User) -> set[str] | None:
        """The stores an area manager looks after; None means all of them."""
        if user.role != "area_manager" or not user.area_id:
            return None
        area = self._areas.get(user.area_id)
        return set(area.stores) if area else set()

    def _visible(self, user: User, s: Suggestion) -> bool:
        if user.role == "area_manager":
            stores = self._area_stores(user)
            return stores is None or s.store_id in stores
        if user.role == "store_manager":
            return s.store_id == user.store_id
        return s.approver_role == user.role

    # ---- health and kill switch ----------------------------------------------------------

    def health(self) -> HealthResponse:
        try:
            return HealthResponse(status="ok", kill_switch=self.storage.kill_switch_on())
        except Exception:
            # cannot read the switch: say degraded and behave as if suggestions are off
            return HealthResponse(status="degraded", kill_switch=True)

    def set_kill_switch(self, user: User, on: bool) -> KillSwitchResponse:
        self.require_role(user, "area_manager")
        if user.area_id:
            raise ApiError(403, "only the area manager for all stores can stop every suggestion")
        try:
            self.storage.set_kill_switch(on)
            self.storage.append_audit(audit.kill_switch(on, user.actor_id, self.now()))
        except Exception as exc:
            raise ApiError(503, "could not change the kill switch") from exc
        return KillSwitchResponse(status="ok", kill_switch=on)

    def _killed(self) -> bool:
        try:
            return self.storage.kill_switch_on()
        except Exception:
            return True  # fail safe

    # ---- expiry --------------------------------------------------------------------------

    def expire_due(self) -> int:
        """Expire overdue proposals. Only the state changes and one audit event is written."""
        now = self.now()
        count = 0
        for s in self.storage.list_suggestions():
            if due_for_expiry(s, now) and self.storage.transition(s.id, "proposed", "expired"):
                count += 1
                with contextlib.suppress(AlreadyExistsError):
                    self.storage.append_audit(audit.expired(s, now))
        return count

    def _expire_quietly(self) -> None:
        try:
            self.expire_due()
        except Exception:  # expiry is retried on the next call; reading must still work
            return

    # ---- suggestions ---------------------------------------------------------------------

    def list_suggestions(
        self,
        user: User,
        role: Role | None,
        store_id: str | None,
        kind: str | None,
        state: SuggestionState | None,
    ) -> Served[Suggestion]:
        if user.role == "store_manager" and store_id not in (None, user.store_id):
            raise ApiError(403, "a store manager sees only their own store")
        self._expire_quietly()
        served = fallback.attempt(self.storage.list_suggestions)
        killed = self._killed()
        rows = [
            s
            for s in served.items
            if self._visible(user, s)
            and not (killed and s.state == "proposed")  # kill switch: show less
            and role in (None, s.approver_role)
            and store_id in (None, s.store_id)
            and kind in (None, s.payload.kind)
            and state in (None, s.state)
        ]
        rows.sort(key=lambda s: (s.state != "proposed", aware(s.deadline), s.id))
        return Served(rows, served.stale)

    def get_suggestion(self, user: User, suggestion_id: str) -> Suggestion:
        self._expire_quietly()
        try:
            s = self.storage.get_suggestion(suggestion_id)
        except Exception as exc:
            raise ApiError(503, "data is unavailable") from exc
        if s is None or not self._visible(user, s) or (self._killed() and s.state == "proposed"):
            raise ApiError(404, "no such suggestion")
        return s

    def decide(self, user: User, suggestion_id: str, body: Approval) -> Suggestion:
        if self._killed():
            raise ApiError(423, "suggestions are switched off")
        s = self.get_suggestion(user, suggestion_id)
        if not may_decide(s, user.role, user.store_id):
            raise ApiError(403, "only the suggestion's approver can decide")
        if body.actor_role != user.role:
            raise ApiError(403, "actor_role does not match the signed-in role")
        # who and when come from the sign-in and the server clock, not from the caller
        approval = body.model_copy(update={"actor_id": user.actor_id, "at": self.now()})
        try:
            new_state = next_state(s, approval, approval.at)
        except DecisionError as exc:
            if exc.code == "overdue":
                self._expire_quietly()
            raise ApiError(_DECISION_STATUS[exc.code], str(exc)) from exc
        try:
            if not self.storage.transition(s.id, s.state, new_state):
                raise ApiError(409, "the suggestion changed; reload it")
            self.storage.create_approval(approval)
            with contextlib.suppress(AlreadyExistsError):  # a retry after a partial write
                self.storage.append_audit(audit.decision(s, approval))
        except ApiError:
            raise
        except AlreadyExistsError as exc:
            raise ApiError(409, "already decided") from exc
        except Exception as exc:
            raise ApiError(503, "could not record the decision") from exc
        return s.model_copy(update={"state": new_state})

    # ---- forecasts and totals ------------------------------------------------------------

    def forecasts(
        self, user: User, store_id: str | None, sku_id: str | None, on: date | None
    ) -> Served[Forecast]:
        self.require_role(user, "store_manager", "dc_lead")
        if user.role == "store_manager":
            if store_id not in (None, user.store_id):
                raise ApiError(403, "a store manager sees only their own store")
            store_id = user.store_id
        served = fallback.attempt(lambda: self.storage.list_forecasts(store_id, sku_id, on))
        if served.stale:
            return served
        return fallback.fresh_forecasts(served.items, self.now().date())

    def dc_orders(self, user: User) -> DcOrders:
        """What every store has ordered so far, added up per product, plus what the DC bought.

        Information for the DC lead. Nothing here orders, changes or reduces anything.
        """
        self.require_role(user, "dc_lead")
        served = fallback.attempt(self.storage.list_suggestions)
        orders = [
            s for s in served.items if s.payload.kind == "order" and s.state not in ("expired",)
        ]
        if not orders:
            return DcOrders(
                on=None,
                products=[],
                bought=[],
                markets=self._markets,
                all_decided=False,
                stale=served.stale,
            )
        day = max(aware(s.created_at).date() for s in orders)
        todays = [s for s in orders if aware(s.created_at).date() == day]
        per_sku: dict[str, dict[str, float]] = {}
        for s in todays:
            p = s.payload
            assert isinstance(p, OrderPayload)
            row = per_sku.setdefault(
                s.sku_id,
                {"confirmed": 0.0, "waiting": 0.0, "decided": 0, "waiting_n": 0, "rejected": 0},
            )
            if s.state == "proposed":
                row["waiting"] += p.recommended_units
                row["waiting_n"] += 1
            elif s.state == "rejected":
                row["rejected"] += 1
            else:  # approved, edited or done
                units = p.recommended_units
                if s.state == "edited":
                    approval = self.storage.get_approval(s.id)
                    if approval is not None and approval.edited_units is not None:
                        units = approval.edited_units
                row["confirmed"] += units
                row["decided"] += 1
        products = [
            ProductOrders(
                sku_id=sku,
                confirmed_units=round(r["confirmed"], 1),
                waiting_units=round(r["waiting"], 1),
                stores_decided=int(r["decided"]),
                stores_waiting=int(r["waiting_n"]),
                stores_rejected=int(r["rejected"]),
            )
            for sku, r in sorted(per_sku.items())
        ]
        today = self.now().date()
        bought: dict[tuple[str, str, str | None], float] = {}
        for rec in self.storage.list_outcomes("purchase", None, today):
            if rec.source and rec.units_bought:
                key = (rec.sku_id, rec.source, rec.market)
                bought[key] = bought.get(key, 0.0) + rec.units_bought
        return DcOrders(
            on=day,
            products=products,
            bought=[
                BoughtRow(sku_id=k[0], source=k[1], market=k[2], units=v)
                for k, v in sorted(
                    bought.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")
                )
            ],
            markets=self._markets,
            all_decided=all(p.stores_waiting == 0 for p in products),
            stale=served.stale,
        )

    def dc_totals(self, user: User, on: date | None) -> DcTotals:
        self.require_role(user, "dc_lead")
        day = on or self.now().date()
        served = self.forecasts(user, None, None, day)
        if on is None and not served.items and not served.stale:
            # Buying is for tomorrow: the evening run forecasts from the next day on
            tomorrow = self.forecasts(user, None, None, day + timedelta(days=1))
            if tomorrow.items:
                day, served = day + timedelta(days=1), tomorrow
        by_sku: dict[str, list[Forecast]] = {}
        for f in served.items:
            by_sku.setdefault(f.sku_id, []).append(f)
        totals = []
        for sku, rows in sorted(by_sku.items()):
            first = rows[0]
            totals.append(
                ProductTotal(
                    sku_id=sku,
                    demand=Range(
                        low=sum(r.demand.low for r in rows),
                        likely=sum(r.demand.likely for r in rows),
                        high=sum(r.demand.high for r in rows),
                    ),
                    stores=len({r.store_id for r in rows}),
                    flags=sorted({fl for r in rows for fl in r.flags}),
                    demand_estimated=any(r.demand_estimated for r in rows),
                    model_version=first.model_version,
                    data_snapshot_id=first.data_snapshot_id,
                    config_digest=first.config_digest,
                )
            )
        # Trimming is advice about spot (mandi) buying only, never confirmed farmer volume (G03).
        # It is a suggestion, so the kill switch hides it; if it can't be read, show none.
        trimming: list[TrimmingHint] = []
        stale = served.stale
        if not self._killed():
            stored = fallback.attempt(lambda: self.storage.list_trimming(day))
            stale = stale or stored.stale
            trimming = [
                TrimmingHint(
                    sku_id=t.sku_id, spot_units_to_trim=t.spot_units_to_trim, reason=t.reason
                )
                for t in stored.items
            ]
        return DcTotals(on=day, totals=totals, trimming=trimming, stale=stale)

    def projections(
        self, user: User, store_id: str | None, sku_id: str | None
    ) -> Served[Projection]:
        self.require_role(user, "store_manager", "area_manager", "dc_lead")
        if user.role == "store_manager":
            if store_id not in (None, user.store_id):
                raise ApiError(403, "a store manager sees only their own store")
            store_id = user.store_id
        served = fallback.attempt(lambda: self.storage.list_projections(store_id, sku_id))
        if served.stale:
            return served
        return fallback.fresh_projections(served.items, self.now().date())

    # ---- prices, farmers, scorecard, audit -----------------------------------------------

    def get_prices(self, user: User, sku_id: str | None) -> Served[PriceQuote]:
        self.require_role(user, "dc_lead")
        try:
            quotes = self.prices.fetch(sku_id)
        except Exception:
            stored = fallback.attempt(lambda: self.storage.list_prices(sku_id))
            return Served(fallback.as_stale(stored.items), stale=True)
        with contextlib.suppress(Exception):  # serving live quotes matters more than caching
            self.storage.put_prices(quotes)
        return Served(quotes)

    def farmer_forecast(self, user: User, fpo_id: str | None) -> Served[FarmerVolumeForecast]:
        self.require_role(user, "farmer_coordinator")
        return fallback.attempt(lambda: self.storage.list_farmer_forecasts(fpo_id))

    def scorecard(self, user: User, scope: str | None) -> Served[Scorecard]:
        self.require_role(user, "area_manager")
        stores = self._area_stores(user)

        def rows() -> list[Scorecard]:
            found = _latest_per_scope(self.storage.list_scorecards(scope))
            # a chain-wide card covers stores outside this area, so an area sees its stores only
            return found if stores is None else [c for c in found if c.scope in stores]

        return fallback.attempt(rows)

    def recorded_scorecard(self, user: User) -> Served[Scorecard]:
        """Waste, empty shelves and farmer share from what people recorded, not the data pack."""
        self.require_role(user, "area_manager")
        today, days = self.now().date(), self.scorecard_days
        stores = self._area_stores(user)

        def rows() -> list[Scorecard]:
            records = self.storage.list_outcomes()
            if stores is not None:
                records = [r for r in records if r.kind == "closing" and r.store_id in stores]
            cards = scorecards_from_outcomes(records, today, days)
            return cards if stores is None else [c for c in cards if c.scope in stores]

        return fallback.attempt(rows)

    def contacts(self, user: User) -> list[StoreContact]:
        """Who to call at each store: the area manager only (staff details are not for everyone)."""
        self.require_role(user, "area_manager")
        stores = self._area_stores(user)
        return [c for c in self._contacts if stores is None or c.store_id in stores]

    def audit_log(self, user: User, suggestion_id: str | None) -> Served[AuditEvent]:
        self.require_role(user, "area_manager")
        stores = self._area_stores(user)

        def rows() -> list[AuditEvent]:
            events = self.storage.list_audit(suggestion_id)
            if stores is None:
                return events
            mine = {s.id for s in self.storage.list_suggestions() if s.store_id in stores}
            return [e for e in events if e.suggestion_id in mine]

        return fallback.attempt(rows)

    # ---- outcomes ------------------------------------------------------------------------

    def record_outcome(self, user: User, body: OutcomeInput) -> OutcomeRecord:
        """A person enters what really happened: a fact, so the kill switch does not stop it."""
        if body.kind == "closing":
            self.require_role(user, "store_manager")
            if body.store_id != user.store_id:
                raise ApiError(403, "a store manager records only their own store")
        else:
            self.require_role(user, "dc_lead")
            if body.market is not None and body.market not in self._markets:
                raise ApiError(422, "that is not one of the markets we buy from")
        now = self.now()
        if body.on > now.date():
            raise ApiError(422, "that day has not happened yet")
        try:
            record = OutcomeRecord(**body.model_dump(), recorded_by=user.actor_id, recorded_at=now)
        except ValueError as exc:
            raise ApiError(422, "the numbers do not fit this kind of record") from exc
        try:
            self.storage.put_outcome(record)
            self.storage.append_audit(audit.outcome(record))
        except Exception as exc:
            raise ApiError(503, "could not record this") from exc
        if record.kind == "closing" and record.suggestion_id:
            self._finish_order(record)
        return record

    def _finish_order(self, record: OutcomeRecord) -> None:
        """An approved or edited order of this store and product is done once its day is in."""
        with contextlib.suppress(Exception):  # the record is already saved; this is a label
            s = self.storage.get_suggestion(record.suggestion_id or "")
            if (
                s is not None
                and s.store_id == record.store_id
                and s.sku_id == record.sku_id
                and s.state in ("approved", "edited")
            ):
                self.storage.transition(s.id, s.state, "done")

    def list_outcomes(
        self, user: User, kind: str | None, store_id: str | None, on: date | None
    ) -> Served[OutcomeRecord]:
        self.require_role(user, "store_manager", "dc_lead", "area_manager")
        if user.role == "store_manager":
            if store_id not in (None, user.store_id):
                raise ApiError(403, "a store manager sees only their own store")
            store_id, kind = user.store_id, "closing"
        elif user.role == "dc_lead":
            kind = "purchase"
        area = self._area_stores(user)
        if area is not None:
            if store_id is not None and store_id not in area:
                raise ApiError(403, "that store is not in your area")
            kind = "closing"

        def rows() -> list[OutcomeRecord]:
            found = self.storage.list_outcomes(kind, store_id, on)
            return found if area is None else [r for r in found if r.store_id in area]

        return fallback.attempt(rows)

    # ---- assistant -----------------------------------------------------------------------

    def ask(self, user: User, suggestion_id: str, question: str) -> AskResponse:
        s = self.get_suggestion(user, suggestion_id)
        try:
            return AskResponse(
                suggestion_id=s.id, answer=self.assistant.answer(s, question), source="assistant"
            )
        except Exception:
            # the stored reason is the one sentence we are sure of
            return AskResponse(suggestion_id=s.id, answer=s.reason, source="stored_reason")
