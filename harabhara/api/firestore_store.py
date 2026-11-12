"""Firestore implementation of ``Storage``.

Collections: suggestions, approvals, audit, prices, forecasts, plus farmer_forecasts,
scorecards, trimming, projections and control (the kill switch). Approvals and audit use
``create`` so a second write fails; nothing here updates or deletes them.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from google.api_core import exceptions as gexc
from pydantic import BaseModel

from harabhara.api.storage import (
    AlreadyExistsError,
    farmer_key,
    forecast_key,
    outcome_key,
    price_key,
    projection_key,
    scorecard_key,
    trimming_key,
)
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

SUGGESTIONS = "suggestions"
APPROVALS = "approvals"
AUDIT = "audit"
PRICES = "prices"
FORECASTS = "forecasts"
FARMER_FORECASTS = "farmer_forecasts"
SCORECARDS = "scorecards"
TRIMMING = "trimming"
PROJECTIONS = "projections"
OUTCOMES = "outcomes"
CONTROL = "control"
KILL_SWITCH_DOC = "kill_switch"


def _id(raw: str) -> str:
    return quote(raw, safe="")  # document ids may not contain "/"


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


class FirestoreStorage:
    def __init__(self, client: Any) -> None:
        self._db = client

    @classmethod
    def from_project(cls, project: str | None = None) -> FirestoreStorage:
        from google.cloud import firestore

        return cls(firestore.Client(project=project))

    def _col(self, name: str) -> Any:
        return self._db.collection(name)

    def _create(self, collection: str, doc_id: str, model: BaseModel) -> None:
        try:
            self._col(collection).document(_id(doc_id)).create(_dump(model))
        except gexc.AlreadyExists as exc:
            raise AlreadyExistsError(doc_id) from exc

    def _set_all(self, collection: str, items: list[tuple[str, BaseModel]]) -> None:
        for doc_id, model in items:
            self._col(collection).document(_id(doc_id)).set(_dump(model))

    def _stream[M: BaseModel](self, collection: str, cls: type[M], **equal: str | None) -> list[M]:
        query: Any = self._col(collection)
        for field, value in equal.items():
            if value is not None:
                query = query.where(field, "==", value)
        return [cls.model_validate(doc.to_dict()) for doc in query.stream()]

    # suggestions
    def get_suggestion(self, suggestion_id: str) -> Suggestion | None:
        snap = self._col(SUGGESTIONS).document(_id(suggestion_id)).get()
        return Suggestion.model_validate(snap.to_dict()) if snap.exists else None

    def list_suggestions(self) -> list[Suggestion]:
        return self._stream(SUGGESTIONS, Suggestion)

    def create_suggestion(self, suggestion: Suggestion) -> None:
        self._create(SUGGESTIONS, suggestion.id, suggestion)

    def transition(
        self, suggestion_id: str, expected: SuggestionState, new: SuggestionState
    ) -> bool:
        ref = self._col(SUGGESTIONS).document(_id(suggestion_id))
        snap = ref.get()
        if not snap.exists or snap.to_dict().get("state") != expected:
            return False
        try:
            # Fails if anyone wrote the document after we read it
            ref.update(
                {"state": new}, option=self._db.write_option(last_update_time=snap.update_time)
            )
        except (gexc.FailedPrecondition, gexc.Aborted):
            return False
        return True

    # approvals and audit
    def create_approval(self, approval: Approval) -> None:
        self._create(APPROVALS, approval.suggestion_id, approval)

    def get_approval(self, suggestion_id: str) -> Approval | None:
        snap = self._col(APPROVALS).document(_id(suggestion_id)).get()
        return Approval.model_validate(snap.to_dict()) if snap.exists else None

    def append_audit(self, event: AuditEvent) -> None:
        self._create(AUDIT, event.id, event)

    def list_audit(self, suggestion_id: str | None = None) -> list[AuditEvent]:
        events = self._stream(AUDIT, AuditEvent, suggestion_id=suggestion_id)
        return sorted(events, key=lambda e: e.at)

    # precomputed outputs
    def put_forecasts(self, forecasts: list[Forecast]) -> None:
        self._set_all(FORECASTS, [(forecast_key(f), f) for f in forecasts])

    def list_forecasts(
        self, store_id: str | None = None, sku_id: str | None = None, on: date | None = None
    ) -> list[Forecast]:
        return self._stream(
            FORECASTS,
            Forecast,
            store_id=store_id,
            sku_id=sku_id,
            target_date=on.isoformat() if on else None,
        )

    def put_prices(self, quotes: list[PriceQuote]) -> None:
        self._set_all(PRICES, [(price_key(q), q) for q in quotes])

    def list_prices(self, sku_id: str | None = None) -> list[PriceQuote]:
        return self._stream(PRICES, PriceQuote, sku_id=sku_id)

    def put_farmer_forecasts(self, rows: list[FarmerVolumeForecast]) -> None:
        self._set_all(FARMER_FORECASTS, [(farmer_key(r), r) for r in rows])

    def list_farmer_forecasts(self, fpo_id: str | None = None) -> list[FarmerVolumeForecast]:
        return self._stream(FARMER_FORECASTS, FarmerVolumeForecast, fpo_id=fpo_id)

    def put_scorecards(self, rows: list[Scorecard]) -> None:
        self._set_all(SCORECARDS, [(scorecard_key(s), s) for s in rows])

    def list_scorecards(self, scope: str | None = None) -> list[Scorecard]:
        return self._stream(SCORECARDS, Scorecard, scope=scope)

    def put_trimming(self, rows: list[TrimmingSuggestion]) -> None:
        keep = {_id(trimming_key(r)) for r in rows}
        for day in {r.on for r in rows}:
            for doc in self._col(TRIMMING).where("on", "==", day.isoformat()).stream():
                if doc.id not in keep:
                    doc.reference.delete()
        self._set_all(TRIMMING, [(trimming_key(r), r) for r in rows])

    def list_trimming(self, on: date | None = None) -> list[TrimmingSuggestion]:
        rows = self._stream(TRIMMING, TrimmingSuggestion, on=on.isoformat() if on else None)
        return sorted(rows, key=lambda t: (t.on, t.sku_id))

    def put_projections(self, rows: list[Projection]) -> None:
        self._set_all(PROJECTIONS, [(projection_key(p), p) for p in rows])

    def list_projections(
        self, store_id: str | None = None, sku_id: str | None = None
    ) -> list[Projection]:
        return self._stream(PROJECTIONS, Projection, store_id=store_id, sku_id=sku_id)

    # outcomes
    def put_outcome(self, record: OutcomeRecord) -> None:
        self._set_all(OUTCOMES, [(outcome_key(record), record)])

    def list_outcomes(
        self,
        kind: str | None = None,
        store_id: str | None = None,
        on: date | None = None,
        since: date | None = None,
    ) -> list[OutcomeRecord]:
        if since is not None:
            # one range on a single field needs no composite index; the rest is filtered here
            query = self._col(OUTCOMES).where("on", ">=", since.isoformat())
            found = [OutcomeRecord.model_validate(doc.to_dict()) for doc in query.stream()]
            rows = [
                r
                for r in found
                if kind in (None, r.kind) and store_id in (None, r.store_id) and on in (None, r.on)
            ]
        else:
            rows = self._stream(
                OUTCOMES,
                OutcomeRecord,
                kind=kind,
                store_id=store_id,
                on=on.isoformat() if on else None,
            )
        return sorted(rows, key=lambda r: (r.on, r.store_id or "", r.sku_id, r.source or ""))

    # control
    def kill_switch_on(self) -> bool:
        snap = self._col(CONTROL).document(KILL_SWITCH_DOC).get()
        return bool(snap.exists and snap.to_dict().get("on"))

    def set_kill_switch(self, on: bool) -> None:
        self._col(CONTROL).document(KILL_SWITCH_DOC).set({"on": on})
