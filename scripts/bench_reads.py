"""Times the slow screens' calls against the real database, with and without the in-memory snapshot.

    uv run python -m scripts.bench_reads

Read only from the person's side (it signs in with test PINs it creates itself). The server's usual
expiry of overdue suggestions runs on reads, exactly as it does in production.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from harabhara.api.app import create_app
from harabhara.api.firestore_store import FirestoreStorage
from harabhara.api.settings import ApiSettings, User
from harabhara.api.snapshot import SnapshotStorage
from harabhara.settings import load_config

PINS = {
    "1111": User("bench-store", "store_manager", "S01"),
    "3333": User("bench-area", "area_manager"),
}
CALLS = [
    ("1111", "evening orders", "/suggestions?role=store_manager&store_id=S01&kind=order"),
    ("1111", "morning alerts", "/suggestions?role=store_manager&store_id=S01&state=proposed"),
    ("1111", "my numbers week", "/history/series?period=week"),
    ("1111", "my numbers month", "/history/series?period=month"),
    ("1111", "a past day", "/history/day?date=2026-11-10"),
    ("3333", "approvals queue", "/suggestions?role=area_manager&state=proposed"),
    ("3333", "store cards", "/history/week"),
    ("3333", "numbers week", "/history/series?period=week"),
    ("3333", "numbers month", "/history/series?period=month"),
]


def run(label: str, storage) -> dict[str, tuple[float, float]]:  # type: ignore[no-untyped-def]
    settings = ApiSettings(signing_key="bench", pins=PINS)
    client = TestClient(create_app(storage, settings))
    tokens = {
        pin: {
            "Authorization": "Bearer "
            + client.post("/api/v1/auth/login", json={"pin": pin}).json()["token"]
        }
        for pin in PINS
    }
    out: dict[str, tuple[float, float]] = {}
    for pin, name, path in CALLS:
        times = []
        for _ in range(2):
            t = time.perf_counter()
            r = client.get("/api/v1" + path, headers=tokens[pin])
            times.append(time.perf_counter() - t)
            assert r.status_code == 200, (name, r.status_code, r.text[:200])
        out[name] = (times[0], times[1])
    return out


if __name__ == "__main__":
    project = "agents-mu"
    pipe = load_config().modeling.pipeline
    before = run("plain", FirestoreStorage.from_project(project))
    snap = SnapshotStorage(
        FirestoreStorage.from_project(project),
        retention_days=pipe.history_days_back,
        refresh_seconds=pipe.snapshot_refresh_seconds,
    )
    t0 = time.perf_counter()
    snap.warm()
    warm = time.perf_counter() - t0
    after = run("snapshot", snap)
    print(f"{'':20}{'database each time':>22}{'from memory, 1st':>20}{'2nd':>8}")
    for name in before:
        print(f"{name:20}{before[name][1]:>21.2f}s{after[name][0]:>19.2f}s{after[name][1]:>7.2f}s")
    print(f"\nloading the snapshot once at start-up: {warm:.1f}s")
