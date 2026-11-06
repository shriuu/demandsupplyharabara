"""The scheduled daily job: run the pipeline for one data day and load it for the screens.

The data pack ends in the past, so each calendar day shows one data day (cycling through a
window of training days) as "today", exactly as ``pipeline.run --demo-today`` does. Running
twice on the same day picks the same data day and the same ids, and the loader skips ids it
already holds, so a repeat changes nothing and never undoes a decision.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from harabhara.api.loader import load_directory
from harabhara.api.storage import Storage
from harabhara.pipeline.forecast import fit_forecaster
from harabhara.pipeline.inputs import last_training_day, load_pack
from harabhara.pipeline.run import (
    _tz,
    build_outputs,
    check_not_holdout,
    shift_to_today,
    write_outputs,
)
from harabhara.settings.loader import load_config

DATA_DIR_ENV = "HARABHARA_DATA_DIR"
DEFAULT_DATA_DIR = "/data"


@dataclass(frozen=True)
class DailyResult:
    today: date
    data_day: date
    created: int
    existing: int


def pick_data_day(today: date, last_training: date, window_days: int) -> date:
    """The data day shown as ``today``: one per calendar day, inside the training period."""
    first = last_training - timedelta(days=window_days - 1)
    return first + timedelta(days=today.toordinal() % window_days)


def run_daily(
    data_dir: Path, storage: Storage, out_dir: Path, now: datetime | None = None
) -> DailyResult:
    cfg = load_config()
    pack = load_pack(data_dir, cfg)
    now = now or datetime.now(_tz(pack))
    last_training = last_training_day(pack.panel)
    pipeline = cfg.modeling.pipeline
    day = pick_data_day(now.date(), last_training, pipeline.daily_demo_window_days)
    check_not_holdout(day, last_training)
    fc = fit_forecaster(pack, day - timedelta(days=1))
    out = build_outputs(pack, fc, day)
    out = shift_to_today(
        out, now.date() - day, f"demo{now:%Y%m%d}", now, pipeline.demo_keep_open_hours
    )
    write_outputs(out, out_dir)
    report = load_directory(storage, out_dir, now)
    return DailyResult(now.date(), day, report.suggestions_created, report.suggestions_existing)


def main() -> None:  # pragma: no cover - thin entrypoint over the tested function
    from harabhara.api.firestore_store import FirestoreStorage
    from harabhara.api.settings import from_env

    storage = FirestoreStorage.from_project(from_env().firestore_project)
    with tempfile.TemporaryDirectory() as out:
        result = run_daily(Path(os.environ.get(DATA_DIR_ENV, DEFAULT_DATA_DIR)), storage, Path(out))
    print(result)


if __name__ == "__main__":  # pragma: no cover
    main()
