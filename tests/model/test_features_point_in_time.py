"""No feature may use data from after the forecast origin (CLAUDE.md s13, data tests)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from harabhara.features.build import feature_columns, make_examples
from harabhara.settings import load_config

PARAMS = load_config().modeling.demand
DAYS = 90


def _panel(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=DAYS)
    rows = []
    for store, fmt in (("S01", "Store"), ("D01", "Dark store")):
        for sku in ("P01", "P13"):
            demand = rng.integers(20, 120, DAYS).astype(float)
            frame = pd.DataFrame(
                {
                    "store_id": store,
                    "sku_id": sku,
                    "date": dates,
                    "demand": demand,
                    "sold": demand * 0.95,
                    "in_season": True,
                    "stockout_flag": rng.random(DAYS) < 0.1,
                    "demand_estimated": False,
                    "usable_for_targets": True,
                    "selling_price": rng.integers(20, 60, DAYS).astype(float),
                    "promo_flag": rng.random(DAYS) < 0.1,
                    "modal_price_inr": rng.uniform(10, 40, DAYS),
                    "arrivals_tonnes": rng.uniform(40, 90, DAYS),
                    "split": "train",
                    "format": fmt,
                    "category": "Vegetables",
                    "size_index": 1.0,
                    "chilled_display": 1,
                    "festival_sensitive": 0,
                }
            )
            rows.append(frame)
    panel = pd.concat(rows, ignore_index=True)
    panel["dow"] = panel["date"].dt.dayofweek
    panel["is_weekend"] = (panel["dow"] >= 5).astype(int)
    panel["day_of_month"] = panel["date"].dt.day
    panel["is_month_start_payday"] = (panel["day_of_month"] <= 3).astype(int)
    panel["school_holiday"] = 0
    panel["festival_intensity_day"] = np.where(panel["day_of_month"] == 20, 1.0, 0.0)
    panel["max_temp_c"] = 28.0
    panel["min_temp_c"] = 18.0
    panel["rainfall_mm"] = 0.0
    panel["humidity_pct"] = 60
    panel["heavy_rain_flag"] = 0
    return panel.sort_values(["store_id", "sku_id", "date"]).reset_index(drop=True)


def test_every_horizon_is_built_and_targets_line_up() -> None:
    panel = _panel()
    examples = make_examples(panel, PARAMS, horizons=3)
    assert sorted(examples["horizon"].unique()) == [1, 2, 3]
    row = examples[
        (examples["store_id"] == "S01")
        & (examples["sku_id"] == "P01")
        & (examples["horizon"] == 2)
        & (examples["origin"] == pd.Timestamp("2026-02-01"))
    ].iloc[0]
    truth = panel[
        (panel["store_id"] == "S01")
        & (panel["sku_id"] == "P01")
        & (panel["date"] == pd.Timestamp("2026-02-03"))
    ].iloc[0]
    assert row["target_date"] == pd.Timestamp("2026-02-03")
    assert row["y_demand"] == truth["demand"]


def test_features_for_an_origin_ignore_everything_after_it() -> None:
    panel = _panel()
    cutoff = pd.Timestamp("2026-02-15")
    baseline = make_examples(panel, PARAMS, horizons=3)

    rng = np.random.default_rng(99)
    altered = panel.copy()
    future = altered["date"] > cutoff
    for column in ("demand", "sold", "selling_price", "modal_price_inr", "arrivals_tonnes"):
        altered.loc[future, column] = rng.uniform(1000, 5000, future.sum())
    altered.loc[future, "stockout_flag"] = ~altered.loc[future, "stockout_flag"]
    altered.loc[future, "promo_flag"] = ~altered.loc[future, "promo_flag"]
    changed = make_examples(altered, PARAMS, horizons=3)

    # Calendar and weather of the target day are known in advance; history features are not.
    history = [
        c for c in feature_columns(baseline) if not c.startswith("t_") and c not in ("horizon",)
    ]
    keys = ["store_id", "sku_id", "origin", "horizon"]
    a = baseline[baseline["origin"] <= cutoff].sort_values(keys).reset_index(drop=True)
    b = changed[changed["origin"] <= cutoff].sort_values(keys).reset_index(drop=True)
    assert len(a) == len(b) > 0
    pd.testing.assert_frame_equal(a[history], b[history])


def test_changing_the_past_does_change_the_features() -> None:
    """Guard against a vacuous test: features must react to history that is legitimately known."""
    panel = _panel()
    altered = panel.copy()
    altered.loc[altered["date"] == pd.Timestamp("2026-02-14"), "demand"] += 500
    a = make_examples(panel, PARAMS, horizons=1)
    b = make_examples(altered, PARAMS, horizons=1)
    origin = pd.Timestamp("2026-02-15")
    row_a = a[(a["origin"] == origin) & (a["store_id"] == "S01") & (a["sku_id"] == "P01")]
    row_b = b[(b["origin"] == origin) & (b["store_id"] == "S01") & (b["sku_id"] == "P01")]
    assert row_a["demand_lag_1"].iloc[0] != row_b["demand_lag_1"].iloc[0]


def test_targets_and_target_flags_are_never_features() -> None:
    examples = make_examples(_panel(), PARAMS, horizons=3)
    columns = set(feature_columns(examples))
    assert not columns & {"y_demand", "y_sold", "t_split", "t_stockout", "t_usable", "target_date"}
    assert {"store_id", "sku_id", "horizon"} <= columns


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_same_weekday_lag_is_never_in_the_future(horizon: int) -> None:
    panel = _panel()
    examples = make_examples(panel, PARAMS, horizons=3)
    row = examples[
        (examples["store_id"] == "S01")
        & (examples["sku_id"] == "P01")
        & (examples["horizon"] == horizon)
        & (examples["origin"] == pd.Timestamp("2026-02-20"))
    ].iloc[0]
    target = row["target_date"]
    source_date = target - pd.Timedelta(days=7)
    expected = panel[
        (panel["store_id"] == "S01") & (panel["sku_id"] == "P01") & (panel["date"] == source_date)
    ]["demand"].iloc[0]
    assert source_date <= row["origin"]
    assert row["demand_same_weekday_1w"] == expected
