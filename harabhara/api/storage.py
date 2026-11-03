"""Storage interface. Firestore in production, an in-memory fake in every test.

The audit log and approvals are create-only: there is no method that updates or deletes them.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Protocol

from harabhara.contracts import (
    Approval,
    AuditEvent,
    FarmerVolumeForecast,
    Forecast,
    PriceQuote,
    Scorecard,
    Suggestion,
    SuggestionState,
)


class AlreadyExistsError(Exception):
    """A create-only write found the record already there."""


class Storage(Protocol):
    # suggestions: created by the loader, then only the state moves
    def get_suggestion(self, suggestion_id: str) -> Suggestion | None: ...
    def list_suggestions(self) -> list[Suggestion]: ...
    def create_suggestion(self, suggestion: Suggestion) -> None:
        """Raises AlreadyExistsError; a loaded or decided suggestion is never overwritten."""
        ...

    def transition(
        self, suggestion_id: str, expected: SuggestionState, new: SuggestionState
    ) -> bool:
        """Atomic compare-and-set on the state. False if the state was not ``expected``."""
        ...

    # approvals and audit: create-only
    def create_approval(self, approval: Approval) -> None: ...
    def get_approval(self, suggestion_id: str) -> Approval | None: ...
    def append_audit(self, event: AuditEvent) -> None:
        """Raises AlreadyExistsError for a repeated id (makes retries safe)."""
        ...

    def list_audit(self, suggestion_id: str | None = None) -> list[AuditEvent]: ...

    # precomputed outputs and prices: replaced by each load
    def put_forecasts(self, forecasts: list[Forecast]) -> None: ...
    def list_forecasts(
        self, store_id: str | None = None, sku_id: str | None = None, on: date | None = None
    ) -> list[Forecast]: ...
    def put_prices(self, quotes: list[PriceQuote]) -> None: ...
    def list_prices(self, sku_id: str | None = None) -> list[PriceQuote]: ...
    def put_farmer_forecasts(self, rows: list[FarmerVolumeForecast]) -> None: ...
    def list_farmer_forecasts(self, fpo_id: str | None = None) -> list[FarmerVolumeForecast]: ...
    def put_scorecards(self, rows: list[Scorecard]) -> None: ...
    def list_scorecards(self, scope: str | None = None) -> list[Scorecard]: ...

    # control
    def kill_switch_on(self) -> bool: ...
    def set_kill_switch(self, on: bool) -> None: ...


def forecast_key(f: Forecast) -> str:
    return f"{f.store_id}|{f.sku_id}|{f.target_date.isoformat()}|{f.horizon_days}"


def price_key(q: PriceQuote) -> str:
    return f"{q.sku_id}|{q.market}|{q.on.isoformat()}"


def farmer_key(r: FarmerVolumeForecast) -> str:
    return f"{r.fpo_id}|{r.sku_id}|{r.on.isoformat()}"


def scorecard_key(s: Scorecard) -> str:
    return f"{s.scope}|{s.period_start.isoformat()}|{s.period_end.isoformat()}"


class InMemoryStorage:
    """Test fake. Same behaviour as the Firestore store, including create-only collections."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._suggestions: dict[str, Suggestion] = {}
        self._approvals: dict[str, Approval] = {}
        self._audit: dict[str, AuditEvent] = {}
        self._forecasts: dict[str, Forecast] = {}
        self._prices: dict[str, PriceQuote] = {}
        self._farmers: dict[str, FarmerVolumeForecast] = {}
        self._scorecards: dict[str, Scorecard] = {}
        self._kill = False

    def get_suggestion(self, suggestion_id: str) -> Suggestion | None:
        return self._suggestions.get(suggestion_id)

    def list_suggestions(self) -> list[Suggestion]:
        return list(self._suggestions.values())

    def create_suggestion(self, suggestion: Suggestion) -> None:
        with self._lock:
            if suggestion.id in self._suggestions:
                raise AlreadyExistsError(suggestion.id)
            self._suggestions[suggestion.id] = suggestion

    def transition(
        self, suggestion_id: str, expected: SuggestionState, new: SuggestionState
    ) -> bool:
        with self._lock:
            current = self._suggestions.get(suggestion_id)
            if current is None or current.state != expected:
                return False
            self._suggestions[suggestion_id] = current.model_copy(update={"state": new})
            return True

    def create_approval(self, approval: Approval) -> None:
        with self._lock:
            if approval.suggestion_id in self._approvals:
                raise AlreadyExistsError(approval.suggestion_id)
            self._approvals[approval.suggestion_id] = approval

    def get_approval(self, suggestion_id: str) -> Approval | None:
        return self._approvals.get(suggestion_id)

    def append_audit(self, event: AuditEvent) -> None:
        with self._lock:
            if event.id in self._audit:
                raise AlreadyExistsError(event.id)
            self._audit[event.id] = event

    def list_audit(self, suggestion_id: str | None = None) -> list[AuditEvent]:
        events = [e for e in self._audit.values() if suggestion_id in (None, e.suggestion_id)]
        return sorted(events, key=lambda e: e.at)

    def put_forecasts(self, forecasts: list[Forecast]) -> None:
        for f in forecasts:
            self._forecasts[forecast_key(f)] = f

    def list_forecasts(
        self, store_id: str | None = None, sku_id: str | None = None, on: date | None = None
    ) -> list[Forecast]:
        return [
            f
            for f in self._forecasts.values()
            if store_id in (None, f.store_id)
            and sku_id in (None, f.sku_id)
            and on in (None, f.target_date)
        ]

    def put_prices(self, quotes: list[PriceQuote]) -> None:
        for q in quotes:
            self._prices[price_key(q)] = q

    def list_prices(self, sku_id: str | None = None) -> list[PriceQuote]:
        return [q for q in self._prices.values() if sku_id in (None, q.sku_id)]

    def put_farmer_forecasts(self, rows: list[FarmerVolumeForecast]) -> None:
        for r in rows:
            self._farmers[farmer_key(r)] = r

    def list_farmer_forecasts(self, fpo_id: str | None = None) -> list[FarmerVolumeForecast]:
        return [r for r in self._farmers.values() if fpo_id in (None, r.fpo_id)]

    def put_scorecards(self, rows: list[Scorecard]) -> None:
        for s in rows:
            self._scorecards[scorecard_key(s)] = s

    def list_scorecards(self, scope: str | None = None) -> list[Scorecard]:
        return [s for s in self._scorecards.values() if scope in (None, s.scope)]

    def kill_switch_on(self) -> bool:
        return self._kill

    def set_kill_switch(self, on: bool) -> None:
        self._kill = on
