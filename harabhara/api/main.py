"""Production wiring: ``uvicorn harabhara.api.main:build_app --factory``."""

from __future__ import annotations

import importlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from harabhara.api.app import create_app
from harabhara.api.firestore_store import FirestoreStorage
from harabhara.api.settings import from_env
from harabhara.api.snapshot import SnapshotStorage
from harabhara.settings import load_config

DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "pwa" / "dist"


def _plug_in(env_name: str) -> Any | None:
    """Optionally build a port from ``package.module:factory`` named in the environment."""
    spec = os.environ.get(env_name)
    if not spec:
        return None
    module, _, factory = spec.partition(":")
    return getattr(importlib.import_module(module), factory)()


def build_app() -> FastAPI:
    settings = from_env()
    if settings.static_dir is None:
        settings = replace(settings, static_dir=DEFAULT_STATIC_DIR)
    pipeline = load_config().modeling.pipeline
    storage = SnapshotStorage(
        FirestoreStorage.from_project(settings.firestore_project),
        retention_days=pipeline.history_days_back,
        refresh_seconds=pipeline.snapshot_refresh_seconds,
        full_refresh_seconds=pipeline.snapshot_full_refresh_seconds,
    )
    storage.warm()  # load before the first request, so nobody waits for it
    return create_app(
        storage,
        settings,
        prices=_plug_in("HARABHARA_PRICE_PORT"),
        assistant=_plug_in("HARABHARA_ASSISTANT_PORT"),
    )
