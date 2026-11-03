from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from harabhara.data.clean import clean_sales, load_sales
from harabhara.models.baselines import same_day_last_week, seven_day_average
from harabhara.settings import load_config
from harabhara.sim.metrics import bias, stockout_rate, wape, wastage_rate

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "work" / "PS-10_store_sales_daily.xlsx"


def test_wape_and_bias() -> None:
    forecast = pd.Series([12.0, 8.0])
    actual = pd.Series([10.0, 10.0])
    assert wape(forecast, actual) == pytest.approx(0.2)
    assert bias(forecast, actual) == pytest.approx(0.0)
    assert bias(pd.Series([12.0, 12.0]), actual) == pytest.approx(0.2)


def test_seven_day_average_uses_only_the_past() -> None:
    df = pd.DataFrame(
        {"store_id": "S01", "sku_id": "P01", "sold": [10.0, 20.0, 30.0, 40.0]},
    )
    avg = seven_day_average(df, window=2)
    assert pd.isna(avg.iloc[0])
    assert list(avg.iloc[1:]) == [10.0, 15.0, 25.0]  # never includes the day itself


def test_same_day_last_week_is_a_seven_day_lag() -> None:
    df = pd.DataFrame({"store_id": "S01", "sku_id": "P01", "sold": [float(n) for n in range(9)]})
    lagged = same_day_last_week(df)
    assert lagged.iloc[7] == 0.0
    assert lagged.iloc[8] == 1.0
    assert lagged.iloc[:7].isna().all()


def test_rates() -> None:
    df = pd.DataFrame(
        {
            "in_season": [True, True, False],
            "stockout_flag": [True, False, False],
            "received_units": [100, 100, 0],
            "wastage_units": [10.0, 6.0, 0.0],
        }
    )
    assert wastage_rate(df) == pytest.approx(0.08)
    assert stockout_rate(df) == pytest.approx(0.5)  # out-of-season rows excluded


@pytest.mark.skipif(not REAL.exists(), reason="data pack is not in the repository")
def test_managers_rule_reproduces_the_briefs_numbers() -> None:
    window = load_config().rules.managers_rule_baseline.avg_window_days
    clean = clean_sales(load_sales(REAL)).data
    df = clean.loc[clean["usable_for_targets"]].sort_values(["store_id", "sku_id", "date"]).copy()
    df["ma"] = seven_day_average(df, window)
    df["lw"] = same_day_last_week(df)
    hold = df[(df["split"] == "holdout")].dropna(subset=["ma", "lw"])
    assert wape(hold["ma"], hold["sold"]) == pytest.approx(0.236, abs=0.002)  # brief: 23.6%
    assert wape(hold["lw"], hold["sold"]) == pytest.approx(0.287, abs=0.002)  # brief: 28.7%
    assert wastage_rate(clean[clean["in_season"]]) == pytest.approx(0.082, abs=0.001)
    assert stockout_rate(clean) == pytest.approx(0.091, abs=0.001)
