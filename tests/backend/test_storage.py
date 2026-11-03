"""One behaviour suite, run against the in-memory fake and the Firestore adapter."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from harabhara.api.firestore_store import FirestoreStorage
from harabhara.api.storage import AlreadyExistsError, InMemoryStorage, Storage
from harabhara.contracts import AuditEvent
from tests.backend.conftest import (
    NOW,
    TODAY,
    farmer_row,
    make_forecast,
    make_quote,
    make_suggestion,
    scorecard_row,
)
from tests.backend.fake_firestore import FakeFirestoreClient

FACTORIES: dict[str, Callable[[], Storage]] = {
    "memory": InMemoryStorage,
    "firestore": lambda: FirestoreStorage(FakeFirestoreClient()),
}


@pytest.fixture(params=sorted(FACTORIES))
def store(request: pytest.FixtureRequest) -> Storage:
    return FACTORIES[request.param]()


def test_suggestion_round_trip_and_ids_with_slashes(store: Storage) -> None:
    s = make_suggestion("store/1/tomato")
    store.create_suggestion(s)
    assert store.get_suggestion("store/1/tomato") == s
    assert store.list_suggestions() == [s]
    assert store.get_suggestion("missing") is None


def test_create_is_create_only(store: Storage) -> None:
    store.create_suggestion(make_suggestion())
    with pytest.raises(AlreadyExistsError):
        store.create_suggestion(make_suggestion())


def test_transition_is_compare_and_set(store: Storage) -> None:
    store.create_suggestion(make_suggestion())
    assert not store.transition("sg-1", "approved", "done")  # wrong expected state
    assert store.transition("sg-1", "proposed", "approved")
    assert not store.transition("sg-1", "proposed", "rejected")  # already moved
    assert not store.transition("nope", "proposed", "approved")
    stored = store.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "approved"


def test_approvals_and_audit_are_create_only(store: Storage) -> None:
    from harabhara.contracts import Approval

    a = Approval(
        suggestion_id="sg-1", action="approve", actor_role="store_manager", actor_id="m", at=NOW
    )
    store.create_approval(a)
    with pytest.raises(AlreadyExistsError):
        store.create_approval(a)
    assert store.get_approval("sg-1") == a

    e = AuditEvent(id="e1", at=NOW, type="approved", suggestion_id="sg-1", actor="m")
    store.append_audit(e)
    with pytest.raises(AlreadyExistsError):
        store.append_audit(e)
    store.append_audit(e.model_copy(update={"id": "e2", "suggestion_id": "sg-2"}))
    assert [x.id for x in store.list_audit("sg-1")] == ["e1"]
    assert len(store.list_audit()) == 2


def test_forecast_filters(store: Storage) -> None:
    store.put_forecasts([make_forecast("S1", "tomato"), make_forecast("S2", "tomato")])
    store.put_forecasts([make_forecast("S1", "tomato")])  # put again: replaced, not duplicated
    assert len(store.list_forecasts()) == 2
    assert [f.store_id for f in store.list_forecasts(store_id="S2")] == ["S2"]
    assert store.list_forecasts(sku_id="onion") == []
    assert len(store.list_forecasts(on=TODAY)) == 2


def test_prices_farmers_scorecards_round_trip(store: Storage) -> None:
    store.put_prices([make_quote(), make_quote("unavailable").model_copy(update={"sku_id": "x"})])
    assert [q.sku_id for q in store.list_prices("x")] == ["x"]
    assert len(store.list_prices()) == 2
    store.put_farmer_forecasts([farmer_row()])
    assert store.list_farmer_forecasts("fpo-1") == [farmer_row()]
    assert store.list_farmer_forecasts("other") == []
    store.put_scorecards([scorecard_row()])
    assert store.list_scorecards("S1") == [scorecard_row()]


def test_kill_switch_defaults_off_and_persists(store: Storage) -> None:
    assert not store.kill_switch_on()
    store.set_kill_switch(True)
    assert store.kill_switch_on()
    store.set_kill_switch(False)
    assert not store.kill_switch_on()


def test_firestore_transition_loses_to_a_concurrent_write() -> None:
    client = FakeFirestoreClient()
    store = FirestoreStorage(client)
    store.create_suggestion(make_suggestion())
    doc = client.collection("suggestions").document("sg-1")
    original_update = doc.__class__.update

    def racing_update(self, data, option=None):  # type: ignore[no-untyped-def]
        self.set({**self.get().to_dict(), "state": "rejected"})  # someone else wins first
        original_update(self, data, option)

    doc.__class__.update = racing_update  # type: ignore[method-assign]
    try:
        assert not store.transition("sg-1", "proposed", "approved")
    finally:
        doc.__class__.update = original_update  # type: ignore[method-assign]
    stored = store.get_suggestion("sg-1")
    assert stored is not None
    assert stored.state == "rejected"
