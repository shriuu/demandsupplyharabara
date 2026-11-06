"""Store manager contact details for the area manager's screen. Read from ``config/contacts.yaml``.

Kept apart from the rules config: it is not a limit, and it must never be needed to start the app.
A missing file or an empty number means "no call button", never a made-up number.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from harabhara.settings.loader import default_config_dir


class StoreContact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    store_id: str
    name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 ]{5,18}$")


def load_contacts(config_dir: Path | None = None) -> list[StoreContact]:
    path = (config_dir or default_config_dir()) / "contacts.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    stores = data.get("stores") or {}
    return [StoreContact(store_id=str(sid), **(row or {})) for sid, row in stores.items()]
