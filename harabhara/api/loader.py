"""Load precomputed model output (JSON files) into storage. Repeat-safe.

Files in the directory, each a JSON list of the matching contract type (all optional):
``forecasts.json``, ``suggestions.json``, ``farmer_forecasts.json``, ``scorecards.json``,
``trimming.json``, ``projections.json``.

Loading never overwrites a suggestion that exists, so a decision is never undone. While the kill
switch is on, no new suggestion is loaded.
"""

from __future__ import annotations

import argparse
import contextlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from harabhara.api.storage import AlreadyExistsError, Storage
from harabhara.contracts import (
    FarmerVolumeForecast,
    Forecast,
    Projection,
    Scorecard,
    Suggestion,
    TrimmingSuggestion,
)
from harabhara.workflow import audit
from harabhara.workflow.deadlines import LOCAL_TZ


@dataclass
class LoadReport:
    forecasts: int = 0
    suggestions_created: int = 0
    suggestions_existing: int = 0
    suggestions_superseded: int = 0
    suggestions_blocked_by_kill_switch: int = 0
    farmer_forecasts: int = 0
    scorecards: int = 0
    projections: int = 0
    trimming: int = 0
    trimming_blocked_by_kill_switch: int = 0


def _read[M](directory: Path, name: str, model: type[M]) -> list[M]:
    path = directory / name
    if not path.is_file():
        return []
    return TypeAdapter(list[model]).validate_python(json.loads(path.read_text(encoding="utf-8")))  # type: ignore[valid-type]


def load_directory(storage: Storage, directory: Path, now: datetime | None = None) -> LoadReport:
    at = now or datetime.now(LOCAL_TZ)
    report = LoadReport()

    forecasts = _read(directory, "forecasts.json", Forecast)
    suggestions = _read(directory, "suggestions.json", Suggestion)
    farmers = _read(directory, "farmer_forecasts.json", FarmerVolumeForecast)
    scorecards = _read(directory, "scorecards.json", Scorecard)
    trimming = _read(directory, "trimming.json", TrimmingSuggestion)
    projections = _read(directory, "projections.json", Projection)

    # everything is validated before the first write
    for s in suggestions:
        if s.state != "proposed":
            msg = f"suggestion {s.id} must be loaded as proposed, not {s.state}"
            raise ValueError(msg)

    storage.put_forecasts(forecasts)
    report.forecasts = len(forecasts)
    storage.put_farmer_forecasts(farmers)
    report.farmer_forecasts = len(farmers)
    storage.put_scorecards(scorecards)
    report.scorecards = len(scorecards)

    storage.put_projections(projections)
    report.projections = len(projections)

    killed = storage.kill_switch_on()
    # trimming is advice to a person, so like any suggestion it is not loaded while switched off
    if killed:
        report.trimming_blocked_by_kill_switch = len(trimming)
    else:
        storage.put_trimming(trimming)
        report.trimming = len(trimming)
    for s in suggestions:
        if killed:
            report.suggestions_blocked_by_kill_switch += 1
            continue
        try:
            storage.create_suggestion(s)
        except AlreadyExistsError:
            report.suggestions_existing += 1
            continue
        report.suggestions_created += 1
        with contextlib.suppress(AlreadyExistsError):
            storage.append_audit(audit.suggestion_created(s, at, "loader"))
    if not killed:
        report.suggestions_superseded = _retire_older(storage, suggestions, at)
    return report


def _retire_older(storage: Storage, loaded: list[Suggestion], at: datetime) -> int:
    """Close proposals that a newer run has replaced, so a store sees one order per product.

    A newer run's suggestion for the same store, product and kind replaces an older proposal that
    nobody has decided: the older one expires, with an audit event saying why. Decided
    suggestions are never touched, and nothing newer than this load is retired.
    """
    if not loaded:
        return 0
    newest = max(s.created_at for s in loaded)
    ids = {s.id for s in loaded}
    keys = {(s.store_id, s.sku_id, s.payload.kind) for s in loaded}
    retired = 0
    for old in storage.list_suggestions():
        if (
            old.state == "proposed"
            and old.id not in ids
            and (old.store_id, old.sku_id, old.payload.kind) in keys
            and old.created_at < newest
            and storage.transition(old.id, "proposed", "expired")
        ):
            retired += 1
            with contextlib.suppress(AlreadyExistsError):
                storage.append_audit(audit.superseded(old, at))
    return retired


def main() -> None:  # pragma: no cover - thin CLI over the tested function
    from harabhara.api.firestore_store import FirestoreStorage
    from harabhara.api.settings import from_env

    parser = argparse.ArgumentParser(description="Load precomputed output into Firestore")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = load_directory(
        FirestoreStorage.from_project(from_env().firestore_project), args.directory
    )
    print(report)


if __name__ == "__main__":  # pragma: no cover
    main()
