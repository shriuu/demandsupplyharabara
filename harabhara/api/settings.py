"""Runtime settings for the service, read from the environment (set by Cloud Run)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

Role = Literal["store_manager", "area_manager", "dc_lead", "farmer_coordinator"]
ROLES: tuple[str, ...] = ("store_manager", "area_manager", "dc_lead", "farmer_coordinator")


@dataclass(frozen=True)
class User:
    actor_id: str
    role: Role
    store_id: str | None = None
    # An area manager looks after one area; None means every store.
    area_id: str | None = None


@dataclass(frozen=True)
class ApiSettings:
    signing_key: str | None = None
    # PIN -> user. Comes from a secret; the repo holds no PINs.
    pins: dict[str, User] = field(default_factory=dict)
    token_ttl_seconds: int = 12 * 3600
    max_failed_logins: int = 5
    login_window_seconds: int = 60
    static_dir: Path | None = None
    firestore_project: str | None = None
    # An online trial only: show the sample sign-ins on the login page. Off unless asked for.
    demo_login: bool = False

    @property
    def sign_in_ready(self) -> bool:
        return bool(self.signing_key and self.pins)


def parse_pins(raw: str) -> dict[str, User]:
    """Parse ``{"1234": {"actor_id": "...", "role": "store_manager", "store_id": "S1"}}``."""
    users: dict[str, User] = {}
    for pin, spec in json.loads(raw).items():
        role = spec["role"]
        if role not in ROLES:
            msg = f"unknown role {role!r}"
            raise ValueError(msg)
        if role == "store_manager" and not spec.get("store_id"):
            msg = "a store_manager needs a store_id"
            raise ValueError(msg)
        if spec.get("area_id") and role != "area_manager":
            msg = "only an area_manager has an area_id"
            raise ValueError(msg)
        users[str(pin)] = User(
            spec["actor_id"], cast(Role, role), spec.get("store_id"), spec.get("area_id")
        )
    return users


def from_env(env: dict[str, str] | None = None) -> ApiSettings:
    e = dict(os.environ) if env is None else env
    static = e.get("HARABHARA_STATIC_DIR")
    return ApiSettings(
        signing_key=e.get("HARABHARA_SIGNING_KEY") or None,
        pins=parse_pins(e["HARABHARA_PIN_DIRECTORY"]) if e.get("HARABHARA_PIN_DIRECTORY") else {},
        static_dir=Path(static) if static else None,
        firestore_project=e.get("GOOGLE_CLOUD_PROJECT") or None,
        demo_login=e.get("HARABHARA_DEMO_LOGIN") == "1",
    )
