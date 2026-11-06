"""Which stores each area manager looks after. Read from ``config/areas.yaml``.

Kept apart from the rules config: it is not a limit. A missing file means one area manager sees
every store, as before. A store in two areas, or an area with no stores, stops the app starting.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from harabhara.settings.loader import default_config_dir


class Area(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    stores: list[str] = Field(min_length=1)


def load_areas(config_dir: Path | None = None) -> dict[str, Area]:
    path = (config_dir or default_config_dir()) / "areas.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    areas = {str(k): Area.model_validate(v) for k, v in (data.get("areas") or {}).items()}
    seen: dict[str, str] = {}
    for area_id, area in areas.items():
        for store in area.stores:
            if store in seen:
                msg = f"store {store} is in both {seen[store]} and {area_id}"
                raise ValueError(msg)
            seen[store] = area_id
    return areas
