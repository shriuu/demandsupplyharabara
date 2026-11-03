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
    make_suggestion,
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
