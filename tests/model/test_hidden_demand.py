from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from harabhara.features.hidden_demand import (
    Hours,
    clock_to_hour,
    estimate_demand,
    share_of_day,
    validate_by_truncation,
)
from harabhara.settings import load_config
from harabhara.settings.schema import HiddenDemandParams

PARAMS = HiddenDemandParams(intraday_profile_gamma=1.0, min_fraction_of_day=0.1)
HOURS = {"Store": Hours(7.0, 22.0), "Dark store": Hours(6.0, 24.0)}


def _rows(**over: object) -> pd.DataFrame:
    base: dict[str, object] = {
        "format": "Store",
        "stockout_flag": True,
        "sold_out_hour": 14.5,
        "sold_corrected": 50.0,
    }
    return pd.DataFrame([base | over])


def test_clock_to_hour() -> None:
    assert clock_to_hour("07:30") == 7.5
    assert clock_to_hour("24:00") == 24.0


def test_share_of_day_is_the_elapsed_fraction() -> None:
    share = share_of_day(pd.Series([14.5]), pd.Series([7.0]), pd.Series([22.0]), PARAMS)
    assert share.iloc[0] == pytest.approx(0.5)


def test_sold_out_at_midday_doubles_the_estimate() -> None:
    out = estimate_demand(_rows(), HOURS, PARAMS)
    assert out["demand"].iloc[0] == pytest.approx(100.0)
    assert bool(out["demand_estimated"].iloc[0]) is True


def test_rows_that_did_not_sell_out_are_untouched() -> None:
    row = _rows(stockout_flag=False, sold_out_hour=float("nan"))
    out = estimate_demand(row, HOURS, PARAMS)
    assert out["demand"].iloc[0] == 50.0
    assert bool(out["demand_estimated"].iloc[0]) is False


def test_estimate_is_never_below_what_was_sold() -> None:
    out = estimate_demand(_rows(sold_out_hour=22.0), HOURS, PARAMS)
    assert out["demand"].iloc[0] >= 50.0


def test_very_early_sell_out_is_bounded() -> None:
    out = estimate_demand(_rows(sold_out_hour=7.1), HOURS, PARAMS)
    assert out["demand"].iloc[0] == pytest.approx(500.0)  # 50 / min_fraction_of_day


def test_dark_stores_use_their_own_hours() -> None:
    out = estimate_demand(_rows(format="Dark store", sold_out_hour=15.0), HOURS, PARAMS)
    assert out["demand"].iloc[0] == pytest.approx(100.0)  # (15-6)/(24-6) = 0.5


def test_input_is_not_modified() -> None:
    rows = _rows()
    before = rows.copy()
    estimate_demand(rows, HOURS, PARAMS)
    pd.testing.assert_frame_equal(rows, before)


def _honest() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "format": rng.choice(["Store", "Dark store"], 400),
            "sold_corrected": rng.integers(20, 200, 400).astype(float),
        }
    )


def test_truncation_recovers_truth_when_the_assumed_pace_is_right() -> None:
    shares = np.array([0.5, 0.7, 0.85, 0.9])
    result = validate_by_truncation(_honest(), HOURS, PARAMS, shares, gamma_true=1.0, seed=1)
    assert result.bias == pytest.approx(0.0, abs=1e-9)


def test_wrong_assumed_pace_shows_up_as_bias_in_the_expected_direction() -> None:
    shares = np.array([0.5, 0.7, 0.85, 0.9])
    front = validate_by_truncation(_honest(), HOURS, PARAMS, shares, gamma_true=0.6, seed=1)
    back = validate_by_truncation(_honest(), HOURS, PARAMS, shares, gamma_true=1.5, seed=1)
    assert front.bias > 0  # more sold early than assumed -> over-estimates
    assert back.bias < 0  # more sold late than assumed -> under-estimates


def test_config_values_load() -> None:
    cfg = load_config().modeling.hidden_demand
    assert cfg.intraday_profile_gamma > 0
    assert 0 < cfg.min_fraction_of_day <= 1
