"""Write the JSON Schema of the shared contracts for the web app's type generator.

Run via ``npm run gen:types`` in ``frontend/pwa``. The output is committed, so the web
build never needs Python.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from harabhara.contracts import (
    Approval,
    AuditEvent,
    FarmerVolumeForecast,
    Forecast,
    PriceQuote,
    Scorecard,
    Suggestion,
)

OUT = Path(__file__).resolve().parents[1] / "frontend/pwa/src/api/contracts.schema.json"


class Contracts(BaseModel):
    """One root so every contract type lands in a single schema."""

    model_config = ConfigDict(title="Contracts")

    forecast: Forecast
    suggestion: Suggestion
    approval: Approval
    audit_event: AuditEvent
    price_quote: PriceQuote
    farmer_volume_forecast: FarmerVolumeForecast
    scorecard: Scorecard


def main() -> None:
    schema = Contracts.model_json_schema(mode="serialization")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
