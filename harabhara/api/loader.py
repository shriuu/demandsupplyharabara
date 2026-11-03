"""Load precomputed model output (JSON files) into storage. Repeat-safe.

Files in the directory, each a JSON list of the matching contract type (all optional):
``forecasts.json``, ``suggestions.json``, ``farmer_forecasts.json``, ``scorecards.json``.

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
from harabhara.contracts import FarmerVolumeForecast, Forecast, Scorecard, Suggestion
from harabhara.workflow import audit
from harabhara.workflow.deadlines import LOCAL_TZ


@dataclass
class LoadReport:
    forecasts: int = 0
    suggestions_created: int = 0
    suggestions_existing: int = 0
    suggestions_blocked_by_kill_switch: int = 0
    farmer_forecasts: int = 0
    scorecards: int = 0


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

    killed = storage.kill_switch_on()
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
    return report


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
