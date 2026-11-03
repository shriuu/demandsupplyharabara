"""G03: only spot (mandi) buying may be trimmed; confirmed farmer volume never is."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from harabhara.rules.guardrails import check_spot_trim


def test_trimming_within_the_spot_volume_is_fine() -> None:
    assert check_spot_trim(trim_units=30, spot_units_available=50) == []


def test_trimming_more_than_the_spot_volume_cuts_into_farmer_volume() -> None:
    (violation,) = check_spot_trim(trim_units=60, spot_units_available=50)
    assert violation.rule == "G03"


@given(trim=st.floats(0, 1000), spot=st.floats(0, 1000))
def test_a_trim_is_allowed_exactly_when_it_fits_inside_the_spot_volume(
    trim: float, spot: float
) -> None:
    assert (check_spot_trim(trim, spot) == []) == (trim <= spot + 1e-9)
