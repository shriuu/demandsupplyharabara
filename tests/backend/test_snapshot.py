"""Recent suggestions and counts are served from memory, and a person's own change shows at once."""

from __future__ import annotations

import contextlib
from datetime import date, datetime, timedelta

from harabhara.api.snapshot import SnapshotStorage
from harabhara.api.storage import InMemoryStorage
from harabhara.contracts import Approval, OutcomeRecord, Suggestion, SuggestionState
from tests.backend.conftest import NOW, TODAY, make_suggestion

WHEN = datetime(2026, 11, 1, 22, 0, tzinfo=NOW.tzinfo)


class Counting(InMemoryStorage):
    """Counts the reads that reach the database."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def list_suggestions(
        self, since: date | None = None, state: SuggestionState | None = None
    ) -> list[Suggestion]:
        self.reads += 1
        return super().list_suggestions(since, state)

    def list_outcomes(
        self,
        kind: str | None = None,
        store_id: str | None = None,
        on: date | None = None,
        since: date | None = None,
    ) -> list[OutcomeRecord]:
        self.reads += 1
        return super().list_outcomes(kind, store_id, on, since)


def closing(day: date, store: str = "S1", sku: str = "tomato", sold: float = 80) -> OutcomeRecord:
    return OutcomeRecord(
        kind="closing", on=day, store_id=store, sku_id=sku, units_sold=sold, units_wasted=5,
        sold_out=False, recorded_by="t", recorded_at=WHEN,
    )  # fmt: skip


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def build(retention: int = 92, refresh: float = 60.0) -> tuple[SnapshotStorage, Counting, Clock]:
    inner, clock = Counting(), Clock()
    snap = SnapshotStorage(
        inner,
        retention_days=retention,
        refresh_seconds=refresh,
        today=lambda: TODAY,
        monotonic=clock,
    )
    return snap, inner, clock


def test_after_the_first_load_reads_do_not_reach_the_database() -> None:
    snap, inner, _ = build()
    inner.create_suggestion(make_suggestion("a"))
    inner.put_outcome(closing(TODAY))
    assert [s.id for s in snap.list_suggestions()] == ["a"]
    assert len(snap.list_outcomes("closing", "S1", None)) == 1
    first = inner.reads
    for _ in range(50):
        snap.list_suggestions()
        snap.list_outcomes(since=TODAY - timedelta(days=30))
    assert inner.reads == first  # fifty more reads of each, none reached the database


def test_a_decision_made_here_shows_at_once_and_is_saved_in_the_database() -> None:
    snap, inner, _ = build()
    inner.create_suggestion(make_suggestion("a"))
    snap.list_suggestions()  # loaded
    assert snap.transition("a", "proposed", "approved") is True
    assert [s.state for s in snap.list_suggestions()] == ["approved"]
    stored = inner.get_suggestion("a")
    assert stored is not None
    assert stored.state == "approved"
    approval = Approval(
        suggestion_id="a", action="approve", actor_role="store_manager", actor_id="x", at=NOW
    )
    snap.create_approval(approval)
    assert inner.get_approval("a") == approval


def test_a_decision_that_loses_the_race_is_refused_and_the_view_is_corrected() -> None:
    snap, inner, _ = build()
    inner.create_suggestion(make_suggestion("a"))
    snap.list_suggestions()
    inner.transition("a", "proposed", "rejected")  # someone else decided, outside this process
    assert snap.list_suggestions()[0].state == "proposed"  # we have not noticed yet
    assert snap.transition("a", "proposed", "approved") is False  # the database says no
    assert snap.list_suggestions()[0].state == "rejected"  # and now we know


def test_a_new_count_and_a_new_suggestion_show_at_once() -> None:
    snap, inner, _ = build()
    snap.list_suggestions()
    snap.create_suggestion(make_suggestion("b"))
    snap.put_outcome(closing(TODAY))
    assert [s.id for s in snap.list_suggestions()] == ["b"]
    assert len(snap.list_outcomes("closing", "S1", TODAY)) == 1
    assert inner.get_suggestion("b") is not None
    assert len(inner.list_outcomes()) == 1


def test_what_another_process_wrote_appears_on_the_first_read_after_the_interval() -> None:
    snap, inner, clock = build(refresh=60)
    snap.list_suggestions()
    inner.create_suggestion(make_suggestion("from-the-daily-job"))
    assert snap.list_suggestions() == []  # not yet
    clock.t += 61
    # the next read does the cheap refresh itself, inside the request: no background thread
    assert [s.id for s in snap.list_suggestions()] == ["from-the-daily-job"]


def test_a_batch_being_retired_is_noticed_by_the_cheap_refresh() -> None:
    """The daily job expires yesterday's waiting proposals when it loads the new batch."""
    snap, inner, clock = build(refresh=60)
    yesterday = make_suggestion("last-night").model_copy(
        update={"created_at": NOW - timedelta(days=1)}
    )
    inner.create_suggestion(yesterday)
    assert [s.state for s in snap.list_suggestions()] == ["proposed"]
    inner.transition("last-night", "proposed", "expired")  # done by another process
    inner.create_suggestion(make_suggestion("tonight"))
    clock.t += 61
    states = {s.id: s.state for s in snap.list_suggestions()}
    assert states == {"last-night": "expired", "tonight": "proposed"}


def test_the_cheap_refresh_does_not_read_everything() -> None:
    snap, inner, clock = build(refresh=60)
    old = make_suggestion("old-decided").model_copy(
        update={"created_at": NOW - timedelta(days=30), "state": "approved"}
    )
    inner.create_suggestion(old)
    snap.list_suggestions()
    inner._suggestions["old-decided"] = old.model_copy(
        update={"state": "rejected"}
    )  # changed outside
    clock.t += 61
    assert (
        snap.list_suggestions()[0].state == "approved"
    )  # a cheap refresh leaves old decided ones alone
    clock.t += 1800
    assert snap.list_suggestions()[0].state == "rejected"  # the full re-read corrects it


def test_a_count_written_by_another_process_appears_after_the_full_re_read() -> None:
    snap, inner, clock = build(refresh=60)
    snap.list_outcomes()
    inner.put_outcome(closing(TODAY))
    clock.t += 61
    assert snap.list_outcomes() == []  # the cheap look does not read counts
    clock.t += 1800
    assert len(snap.list_outcomes()) == 1


def test_a_refresh_that_fails_keeps_the_data_and_waits_for_the_next_interval() -> None:
    snap, inner, clock = build(refresh=60)
    inner.create_suggestion(make_suggestion("a"))
    snap.list_suggestions()
    calls = {"n": 0}
    real = inner.list_suggestions

    def broken(since: date | None = None, state: str | None = None) -> list[Suggestion]:
        calls["n"] += 1
        raise RuntimeError("database unavailable")

    inner.list_suggestions = broken  # type: ignore[method-assign]
    clock.t += 61
    assert [s.id for s in snap.list_suggestions()] == ["a"]  # still served
    snap.list_suggestions()
    snap.list_suggestions()
    assert calls["n"] == 1  # it did not retry on every request
    inner.list_suggestions = real  # type: ignore[method-assign]


def test_a_failed_refresh_keeps_the_previous_data() -> None:
    snap, inner, _ = build()
    inner.create_suggestion(make_suggestion("a"))
    snap.list_suggestions()

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("database unavailable")

    inner.list_suggestions = boom  # type: ignore[method-assign]
    with contextlib.suppress(RuntimeError):
        snap.refresh()
    assert [s.id for s in snap.list_suggestions()] == ["a"]  # still serving what it had


def test_only_the_recent_window_is_held() -> None:
    snap, inner, _ = build(retention=30)
    inner.put_outcome(closing(TODAY - timedelta(days=5)))
    inner.put_outcome(closing(TODAY - timedelta(days=60), sku="onion"))
    assert [r.sku_id for r in snap.list_outcomes()] == ["tomato"]  # the 60 day old count is out
    snap.put_outcome(closing(TODAY - timedelta(days=90), sku="okra"))  # too old to keep in memory
    assert [r.sku_id for r in snap.list_outcomes()] == ["tomato"]
    assert len(inner.list_outcomes()) == 3  # but it is saved


def test_other_reads_go_straight_to_the_database() -> None:
    snap, inner, _ = build()
    assert snap.kill_switch_on() is False
    snap.set_kill_switch(True)
    assert inner.kill_switch_on() is True


def test_an_approval_is_read_from_memory_after_it_is_made_and_never_goes_stale() -> None:
    snap, inner, _ = build()
    inner.create_suggestion(make_suggestion("a"))
    snap.list_suggestions()
    approval = Approval(
        suggestion_id="a", action="edit", actor_role="store_manager", actor_id="x", at=NOW,
        edited_units=25, reason="slow",
    )  # fmt: skip
    snap.create_approval(approval)
    inner._approvals.clear()  # the database is not asked again for this one
    assert snap.get_approval("a") == approval
    assert snap.get_approval("nobody") is None
