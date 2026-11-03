"""Write the API's OpenAPI document for the web app's type generator.

The app factory runs with in-memory storage, so no cloud or network is touched. Run via
``npm run gen:types`` in ``frontend/pwa``; ``tests/test_openapi_file.py`` fails when the
committed file is out of date.
"""

from __future__ import annotations

import json
from pathlib import Path

from harabhara.api.app import create_app
from harabhara.api.settings import ApiSettings
from harabhara.api.storage import InMemoryStorage

OUT = Path(__file__).resolve().parents[1] / "frontend/pwa/src/api/openapi.json"


def build_document() -> str:
    app = create_app(InMemoryStorage(), ApiSettings())
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_document())


if __name__ == "__main__":
    main()
