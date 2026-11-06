"""The loader reads precomputed JSON into storage and is repeat-safe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harabhara.api.loader import load_directory
from harabhara.api.storage import InMemoryStorage
from tests.backend.conftest import (
    NOW,
    farmer_row,
    make_forecast,
    make_projection,
    make_suggestion,
    make_trimming,
    scorecard_row,
)


def write(directory: Path, name: str, rows: list[object]) -> None:
    (directory / name).write_text(
        json.dumps([json.loads(r.model_dump_json()) for r in rows])  # type: ignore[attr-defined]
    )


def test_loads_every_file_and_audits_creation(tmp_path: Path) -> None:
    write(tmp_path, "forecasts.json", [make_forecast()])
    write(tmp_path, "suggestions.json", [make_suggestion("a"), make_suggestion("b")])
    write(tmp_path, "farmer_forecasts.json", [farmer_row()])
    write(tmp_path, "scorecards.json", [scorecard_row()])
    storage = InMemoryStorage()
    report = load_directory(storage, tmp_path, NOW)
    assert (report.forecasts, report.suggestions_created) == (1, 2)
    assert len(storage.list_farmer_forecasts()) == 1
    assert len(storage.list_scorecards()) == 1
    assert sorted(e.type for e in storage.list_audit()) == ["suggestion_created"] * 2


def test_loading_twice_changes_nothing_and_never_undoes_a_decision(tmp_path: Path) -> None:
    write(tmp_path, "suggestions.json", [make_suggestion("a")])
    storage = InMemoryStorage()
    load_directory(storage, tmp_path, NOW)
    assert storage.transition("a", "proposed", "approved")
    again = load_directory(storage, tmp_path, NOW)
    assert again.suggestions_existing == 1
    assert again.suggestions_created == 0
    stored = storage.get_suggestion("a")
    assert stored is not None
    assert stored.state == "approved"
    assert len(storage.list_audit()) == 1


def test_a_missing_directory_content_is_fine(tmp_path: Path) -> None:
    report = load_directory(InMemoryStorage(), tmp_path, NOW)
    assert report.suggestions_created == 0


def test_a_suggestion_without_a_reason_is_rejected_before_any_write(tmp_path: Path) -> None:
    bad = json.loads(make_suggestion("a").model_dump_json())
    bad["reason"] = ""
    (tmp_path / "suggestions.json").write_text(json.dumps([bad]))
    write(tmp_path, "forecasts.json", [make_forecast()])
    storage = InMemoryStorage()
    with pytest.raises(ValueError, match="reason"):
        load_directory(storage, tmp_path, NOW)
    assert storage.list_forecasts() == []


def test_only_proposed_suggestions_can_be_loaded(tmp_path: Path) -> None:
    approved = make_suggestion("a").model_copy(update={"state": "approved"})
    write(tmp_path, "suggestions.json", [approved])
    with pytest.raises(ValueError, match="proposed"):
        load_directory(InMemoryStorage(), tmp_path, NOW)


def test_loads_trimming_and_projections_and_is_repeat_safe(tmp_path: Path) -> None:
    write(tmp_path, "trimming.json", [make_trimming("tomato"), make_trimming("onion")])
    write(tmp_path, "projections.json", [make_projection("S1"), make_projection("S2")])
    storage = InMemoryStorage()
    first = load_directory(storage, tmp_path, NOW)
    assert (first.trimming, first.projections) == (2, 2)
    before = (storage.list_trimming(), storage.list_projections())
    load_directory(storage, tmp_path, NOW)
    assert (storage.list_trimming(), storage.list_projections()) == before


def test_bad_trimming_or_projection_data_is_rejected_before_any_write(tmp_path: Path) -> None:
    write(tmp_path, "forecasts.json", [make_forecast()])
    write(tmp_path, "projections.json", [make_projection()])
    bad = json.loads(make_trimming().model_dump_json())
    bad["spot_units_to_trim"] = -4
    (tmp_path / "trimming.json").write_text(json.dumps([bad]))
    storage = InMemoryStorage()
    with pytest.raises(ValueError, match="spot_units_to_trim"):
        load_directory(storage, tmp_path, NOW)
    assert storage.list_forecasts() == []
    assert storage.list_projections() == []

    (tmp_path / "trimming.json").write_text("[]")
    bad_projection = json.loads(make_projection().model_dump_json())
    bad_projection["days"] = []
    (tmp_path / "projections.json").write_text(json.dumps([bad_projection]))
    with pytest.raises(ValueError, match="days"):
        load_directory(storage, tmp_path, NOW)
    assert storage.list_forecasts() == []


def test_a_newer_run_retires_undecided_older_proposals_for_the_same_product(tmp_path: Path) -> None:
    storage = InMemoryStorage()
    old = make_suggestion("old@demo1")
    write(tmp_path, "suggestions.json", [old])
    load_directory(storage, tmp_path, NOW)
    newer = make_suggestion("new@demo2").model_copy(
        update={"created_at": old.created_at.replace(day=old.created_at.day + 1)}
    )
    write(tmp_path, "suggestions.json", [newer])
    report = load_directory(storage, tmp_path, NOW)
    assert report.suggestions_superseded == 1
    assert storage.get_suggestion("old@demo1").state == "expired"  # type: ignore[union-attr]
    assert storage.get_suggestion("new@demo2").state == "proposed"  # type: ignore[union-attr]
    reasons = [e.data.get("reason") for e in storage.list_audit() if e.type == "expired"]
    assert reasons == ["superseded by a newer run"]


def test_a_decided_proposal_and_other_products_are_never_retired(tmp_path: Path) -> None:
    storage = InMemoryStorage()
    decided = make_suggestion("decided@demo1")
    other_store = make_suggestion("other@demo1", store="S2")
    write(tmp_path, "suggestions.json", [decided, other_store])
    load_directory(storage, tmp_path, NOW)
    assert storage.transition("decided@demo1", "proposed", "approved")
    newer = make_suggestion("new@demo2").model_copy(
        update={"created_at": decided.created_at.replace(day=decided.created_at.day + 1)}
    )
    write(tmp_path, "suggestions.json", [newer])
    report = load_directory(storage, tmp_path, NOW)
    assert report.suggestions_superseded == 0
    assert storage.get_suggestion("decided@demo1").state == "approved"  # type: ignore[union-attr]
    assert storage.get_suggestion("other@demo1").state == "proposed"  # type: ignore[union-attr]


def test_loading_the_same_run_again_retires_nothing(tmp_path: Path) -> None:
    storage = InMemoryStorage()
    write(tmp_path, "suggestions.json", [make_suggestion("a"), make_suggestion("b")])
    load_directory(storage, tmp_path, NOW)
    assert load_directory(storage, tmp_path, NOW).suggestions_superseded == 0
