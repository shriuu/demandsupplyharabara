from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from harabhara.models.cold_start import apply_thin_history


def _frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    forecast = pd.DataFrame(
        {"low": [80.0, 80.0, 80.0], "likely": [100.0, 100.0, 100.0], "high": [120.0] * 3}
    )
    examples = pd.DataFrame({"history_days": [28, 3, 0], "sold_mean_7": [95.0, 20.0, np.nan]})
    return forecast, examples


def test_enough_history_keeps_the_model_forecast() -> None:
    forecast, examples = _frame()
    out = apply_thin_history(forecast, examples, min_history_days=7, range_width=0.5)
    assert list(out.loc[0, ["low", "likely", "high"]]) == [80.0, 100.0, 120.0]
    assert not out.loc[0, "thin_history"]


def test_thin_history_uses_the_recent_average_with_a_fixed_range() -> None:
    forecast, examples = _frame()
    out = apply_thin_history(forecast, examples, min_history_days=7, range_width=0.5)
    assert list(out.loc[1, ["low", "likely", "high"]]) == [10.0, 20.0, 30.0]
    assert out.loc[1, "thin_history"]
    assert not out.loc[1, "no_history"]


def test_no_history_at_all_means_no_forecast_and_says_so() -> None:
    forecast, examples = _frame()
    out = apply_thin_history(forecast, examples, min_history_days=7, range_width=0.5)
    assert out.loc[2, "no_history"]
    assert out["likely"].isna().iloc[2]


def test_input_is_not_modified() -> None:
    forecast, examples = _frame()
    before = forecast.copy()
    apply_thin_history(forecast, examples, min_history_days=7, range_width=0.5)
    pd.testing.assert_frame_equal(forecast, before)


@pytest.mark.parametrize("width", [0.2, 0.5])
def test_range_is_symmetric_around_the_fallback(width: float) -> None:
    forecast, examples = _frame()
    out = apply_thin_history(forecast, examples, min_history_days=7, range_width=width)
    assert float(out["likely"].iloc[1] - out["low"].iloc[1]) == pytest.approx(
        float(out["high"].iloc[1] - out["likely"].iloc[1])
    )


def test_a_product_the_model_never_saw_always_uses_the_fallback() -> None:
    forecast, examples = _frame()
    examples["history_days"] = 28  # plenty of recent history
    unseen = pd.Series([False, True, False])
    out = apply_thin_history(forecast, examples, 7, 0.5, unseen)
    assert list(out["thin_history"]) == [False, True, False]
    assert float(out["likely"].iloc[1]) == float(examples["sold_mean_7"].iloc[1])
