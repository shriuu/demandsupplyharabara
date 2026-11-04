"""G04: waste is never reported without empty shelves and farmer share beside it."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from harabhara.contracts import Scorecard
from harabhara.sim.scorecard import line, together

DAY = date(2026, 8, 5)


def _card(**over: object) -> Scorecard:
    base: dict[str, object] = {
        "scope": "chain",
        "period_start": DAY,
        "period_end": DAY,
        "waste_pct": 7.0,
        "stockout_pct": 9.0,
        "farmer_share": 0.3,
        "farmer_share_definition": "share of purchased volume from farmer groups",
    }
    return together(**{**base, **over})  # type: ignore[arg-type]


def test_a_result_carries_all_three_measures() -> None:
    text = line(_card())
    assert "waste 7.0%" in text
    assert "empty shelves 9.0%" in text
    assert "farmer share 30.0%" in text


def test_waste_without_empty_shelves_is_refused() -> None:
    with pytest.raises(ValueError, match="empty shelves is missing"):
        _card(stockout_pct=None)
    with pytest.raises(ValueError, match="empty shelves is missing"):
        _card(stockout_pct=float("nan"))


def test_empty_shelves_without_waste_is_refused() -> None:
    with pytest.raises(ValueError, match="waste is missing"):
        _card(waste_pct=None)


def test_an_unknown_farmer_share_must_say_why() -> None:
    with pytest.raises(ValidationError, match="must say why"):
        _card(farmer_share=None, farmer_share_definition=None)
    card = _card(farmer_share=None, farmer_share_definition="no purchases recorded")
    assert "farmer share not known" in line(card)


def test_the_contract_cannot_be_built_without_the_three_fields() -> None:
    with pytest.raises(ValidationError):
        Scorecard(scope="x", period_start=DAY, period_end=DAY, waste_pct=1.0)  # type: ignore[call-arg]
