"""The scheduled job picks a data day inside training, the same one all day, and cycles."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from harabhara.jobs.daily import pick_data_day

LAST = date(2026, 8, 5)


@given(
    today=st.dates(min_value=date(2026, 1, 1), max_value=date(2030, 1, 1)),
    window=st.integers(min_value=1, max_value=120),
)
def test_data_day_is_always_inside_the_training_window(today: date, window: int) -> None:
    day = pick_data_day(today, LAST, window)
    assert LAST - timedelta(days=window - 1) <= day <= LAST


def test_same_day_same_data_day_and_next_day_moves_on() -> None:
    today = date(2026, 11, 6)
    assert pick_data_day(today, LAST, 28) == pick_data_day(today, LAST, 28)
    assert pick_data_day(today + timedelta(days=1), LAST, 28) != pick_data_day(today, LAST, 28)


def test_it_cycles_after_one_window() -> None:
    today = date(2026, 11, 6)
    assert pick_data_day(today + timedelta(days=28), LAST, 28) == pick_data_day(today, LAST, 28)
