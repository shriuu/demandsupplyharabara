"""Keeps recent suggestions and recorded counts in memory, so a screen does not read the database.

Why: almost every screen used to read every saved suggestion (thousands) and, for history, every
recorded count (ten thousand or more), then filter in Python. On a small server that took three to
eight seconds a request, and used up the database's read allowance.

How it behaves:
- Reads of suggestions and outcomes come from memory. Everything else goes straight to the database.
- A change made through the app (a decision, a new count) goes to the database first and is then
  put in memory, so the person who made it sees it at once.
- What other processes wrote (the daily job loads a new batch and retires the old one) is picked up
  inside a request, never in a background thread: a small server only gets CPU while it is handling
  a request, so a background refresh barely progressed and new data stayed hidden. A cheap look at
  yesterday, today and everything still waiting runs at most every ``refresh_seconds``, and a full
  re-read every ``full_refresh_seconds``. A failed refresh keeps the old data: show something
  slightly old rather than nothing (guardrail 12).
- Only the recent window is held (the calendar's limit), so memory stays bounded.
- It assumes one server process. With several, a decision on one would not show on another until
  its next refresh. The service is deployed with a single instance for that reason.

Decisions are never made from memory alone: ``transition`` is a compare-and-set in the database, so
a stale view can only lead to "the suggestion changed; reload it", never to a wrong decision.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta

from harabhara.api.storage import Storage, outcome_key
from harabhara.contracts import (
    Approval,
    AuditEvent,
    FarmerVolumeForecast,
    Forecast,
    OutcomeRecord,
    PriceQuote,
    Projection,
    Scorecard,
    Suggestion,
    SuggestionState,
    TrimmingSuggestion,
)

log = logging.getLogger("harabhara.snapshot")
RECENT_LOOKUPS = 100  # old proposals checked one by one in a cheap refresh


class SnapshotStorage:
    def __init__(
        self,
        inner: Storage,
        *,
        retention_days: int,
        refresh_seconds: float,
        full_refresh_seconds: float = 1800.0,
        today: Callable[[], date] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._retention = retention_days
        self._refresh_seconds = refresh_seconds
        self._full_refresh_seconds = full_refresh_seconds
        self._today = today or (lambda: datetime.now().astimezone().date())
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._load_lock = threading.Lock()
        self._suggestions: dict[str, Suggestion] | None = None
        self._outcomes: dict[str, OutcomeRecord] = {}
        self._approvals: dict[str, Approval] = {}
        self._loaded_at = 0.0  # the last refresh of any kind
        self._full_at = 0.0  # the last full re-read
        self._refresh_lock = threading.Lock()

    # ---- loading -------------------------------------------------------------------------

    def _window_start(self) -> date:
        return self._today() - timedelta(days=self._retention)

    def refresh(self) -> None:
        """Re-read the recent window from the database. Keeps the old data if the read fails."""
        start = self._window_start()
        suggestions = {s.id: s for s in self._inner.list_suggestions(since=start)}
        outcomes = {outcome_key(r): r for r in self._inner.list_outcomes(since=start)}
        approvals = {a.suggestion_id: a for a in self._inner.list_approvals(since=start)}
        with self._lock:
            self._suggestions, self._outcomes, self._approvals = suggestions, outcomes, approvals
            self._loaded_at = self._full_at = self._monotonic()

    def warm(self) -> None:
        """Load before the first request. A failure is left for the first read to retry."""
        try:
            self.refresh()
        except Exception:
            log.exception("could not warm the snapshot; the first read will try again")

    def refresh_recent(self) -> None:
        """A cheap look: yesterday's and today's suggestions and everything still waiting.

        Covers a new batch (created today) and the old one being retired (yesterday's proposals
        turning to expired). Proposals older than that which were decided elsewhere are looked up
        one by one, up to a limit; a full re-read catches any beyond it.
        """
        recent_start = self._today() - timedelta(days=1)
        recent = self._inner.list_suggestions(since=recent_start)
        waiting = self._inner.list_suggestions(state="proposed")
        seen = {s.id for s in recent} | {s.id for s in waiting}
        with self._lock:
            held = self._suggestions if self._suggestions is not None else {}
            behind = [i for i, s in held.items() if s.state == "proposed" and i not in seen]
        corrected = [c for i in behind[:RECENT_LOOKUPS] if (c := self._inner.get_suggestion(i))]
        with self._lock:
            if self._suggestions is None:
                return
            for s in [*recent, *waiting, *corrected]:
                self._suggestions[s.id] = s
            self._loaded_at = self._monotonic()

    def _ensure_loaded(self) -> None:
        if self._suggestions is None:
            with self._load_lock:  # one caller loads; the others wait for it
                if self._suggestions is None:
                    self.refresh()
            return
        now = self._monotonic()
        if now - self._full_at > self._full_refresh_seconds:
            self._refresh_now(full=True)
        elif now - self._loaded_at > self._refresh_seconds:
            self._refresh_now(full=False)

    def _refresh_now(self, *, full: bool) -> None:
        """Refresh inside this request; if another one is already at it, serve what we have."""
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            self.refresh() if full else self.refresh_recent()
        except Exception:
            log.exception("snapshot refresh failed; serving the previous data")
            with self._lock:
                self._loaded_at = self._monotonic()  # do not retry on every request
        finally:
            self._refresh_lock.release()

    # ---- suggestions: read from memory, write through -----------------------------------

    def get_suggestion(self, suggestion_id: str) -> Suggestion | None:
        self._ensure_loaded()
        with self._lock:
            held = (self._suggestions or {}).get(suggestion_id)
        return held if held is not None else self._inner.get_suggestion(suggestion_id)

    def list_suggestions(
        self, since: date | None = None, state: SuggestionState | None = None
    ) -> list[Suggestion]:
        self._ensure_loaded()
        with self._lock:
            rows = list((self._suggestions or {}).values())
        return [
            s
            for s in rows
            if (since is None or s.created_at.date() >= since) and state in (None, s.state)
        ]

    def create_suggestion(self, suggestion: Suggestion) -> None:
        self._inner.create_suggestion(suggestion)
        with self._lock:
            if self._suggestions is not None:
                self._suggestions[suggestion.id] = suggestion

    def transition(
        self, suggestion_id: str, expected: SuggestionState, new: SuggestionState
    ) -> bool:
        changed = self._inner.transition(suggestion_id, expected, new)
        with self._lock:
            held = (self._suggestions or {}).get(suggestion_id)
            if changed and held is not None and self._suggestions is not None:
                self._suggestions[suggestion_id] = held.model_copy(update={"state": new})
        if not changed:
            # our view was behind: take the database's version so the next read is right
            latest = self._inner.get_suggestion(suggestion_id)
            with self._lock:
                if latest is not None and self._suggestions is not None:
                    self._suggestions[suggestion_id] = latest
        return changed

    # ---- outcomes: read from memory, write through ---------------------------------------

    def put_outcome(self, record: OutcomeRecord) -> None:
        self._inner.put_outcome(record)
        with self._lock:
            if record.on >= self._window_start():
                self._outcomes[outcome_key(record)] = record

    def list_outcomes(
        self,
        kind: str | None = None,
        store_id: str | None = None,
        on: date | None = None,
        since: date | None = None,
    ) -> list[OutcomeRecord]:
        self._ensure_loaded()
        with self._lock:
            rows = list(self._outcomes.values())
        rows = [
            r
            for r in rows
            if kind in (None, r.kind)
            and store_id in (None, r.store_id)
            and on in (None, r.on)
            and (since is None or r.on >= since)
        ]
        return sorted(rows, key=lambda r: (r.on, r.store_id or "", r.sku_id, r.source or ""))

    # ---- everything else goes straight to the database -----------------------------------

    def create_approval(self, approval: Approval) -> None:
        self._inner.create_approval(approval)
        with self._lock:
            self._approvals[approval.suggestion_id] = approval

    def get_approval(self, suggestion_id: str) -> Approval | None:
        """An approval is never changed once made, so one held in memory is always right."""
        self._ensure_loaded()
        with self._lock:
            held = self._approvals.get(suggestion_id)
        if held is not None:
            return held
        found = self._inner.get_approval(suggestion_id)  # older than the window, or not made yet
        if found is not None:
            with self._lock:
                self._approvals[suggestion_id] = found
        return found

    def list_approvals(self, since: date | None = None) -> list[Approval]:
        self._ensure_loaded()
        with self._lock:
            rows = list(self._approvals.values())
        return rows if since is None else [a for a in rows if a.at.date() >= since]

    def append_audit(self, event: AuditEvent) -> None:
        self._inner.append_audit(event)

    def list_audit(self, suggestion_id: str | None = None) -> list[AuditEvent]:
        return self._inner.list_audit(suggestion_id)

    def put_forecasts(self, forecasts: list[Forecast]) -> None:
        self._inner.put_forecasts(forecasts)

    def list_forecasts(
        self, store_id: str | None = None, sku_id: str | None = None, on: date | None = None
    ) -> list[Forecast]:
        return self._inner.list_forecasts(store_id, sku_id, on)

    def put_prices(self, quotes: list[PriceQuote]) -> None:
        self._inner.put_prices(quotes)

    def list_prices(self, sku_id: str | None = None) -> list[PriceQuote]:
        return self._inner.list_prices(sku_id)

    def put_farmer_forecasts(self, rows: list[FarmerVolumeForecast]) -> None:
        self._inner.put_farmer_forecasts(rows)

    def list_farmer_forecasts(self, fpo_id: str | None = None) -> list[FarmerVolumeForecast]:
        return self._inner.list_farmer_forecasts(fpo_id)

    def put_scorecards(self, rows: list[Scorecard]) -> None:
        self._inner.put_scorecards(rows)

    def list_scorecards(self, scope: str | None = None) -> list[Scorecard]:
        return self._inner.list_scorecards(scope)

    def put_trimming(self, rows: list[TrimmingSuggestion]) -> None:
        self._inner.put_trimming(rows)

    def list_trimming(self, on: date | None = None) -> list[TrimmingSuggestion]:
        return self._inner.list_trimming(on)

    def put_projections(self, rows: list[Projection]) -> None:
        self._inner.put_projections(rows)

    def list_projections(
        self, store_id: str | None = None, sku_id: str | None = None
    ) -> list[Projection]:
        return self._inner.list_projections(store_id, sku_id)

    def kill_switch_on(self) -> bool:
        return self._inner.kill_switch_on()

    def set_kill_switch(self, on: bool) -> None:
        self._inner.set_kill_switch(on)
