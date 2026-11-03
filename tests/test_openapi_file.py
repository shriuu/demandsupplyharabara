"""The committed OpenAPI file (source of the web app's types) matches the running app."""

from __future__ import annotations

from scripts.export_openapi import OUT, build_document


def test_committed_openapi_is_up_to_date() -> None:
    assert OUT.read_text() == build_document(), (
        "frontend/pwa/src/api/openapi.json is stale: run `npm run gen:types` in frontend/pwa"
    )
