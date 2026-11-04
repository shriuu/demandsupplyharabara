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
    DcTotals,
    HealthResponse,
    KillSwitchResponse,
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
    PriceQuote,
    Projection,
    Range,
    Role,
    Scorecard,
    Suggestion,
    SuggestionState,
)
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


class Service:
    def __init__(
        self,
        storage: Storage,
        prices: ports.PricePort,
        assistant: ports.AssistantPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.storage = storage
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

    @staticmethod
    def _visible(user: User, s: Suggestion) -> bool:
        if user.role == "area_manager":
            return True
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
        return fallback.attempt(lambda: self.storage.list_scorecards(scope))

    def audit_log(self, user: User, suggestion_id: str | None) -> Served[AuditEvent]:
        self.require_role(user, "area_manager")
        return fallback.attempt(lambda: self.storage.list_audit(suggestion_id))

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
