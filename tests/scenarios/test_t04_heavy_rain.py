"""T4: heavy rain forecast: lower demand for walk-in stores, higher for dark stores.

Counterfactual on the last four weeks before the as-of day: the same rows are forecast as they
were and again with heavy rain switched on. The model is fit on data before the as-of day only.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from harabhara.pipeline.forecast import _predict_frame, fit_forecaster
from harabhara.pipeline.inputs import PackData, load_pack
from harabhara.settings import load_config

WORK = Path(__file__).resolve().parents[2] / "work"
HAVE_PACK = (WORK / "PS-10_store_sales_daily.xlsx").exists()
AS_OF = date(2026, 8, 5)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository"),
]


@pytest.fixture(scope="module")
def pack() -> PackData:
    return load_pack(WORK, load_config())


def test_heavy_rain_lowers_walk_in_demand_and_does_not_lower_dark_store_demand(
    pack: PackData,
) -> None:
    forecaster = fit_forecaster(pack, AS_OF - timedelta(days=1))
    ex = pack.examples
    rows = ex[
        (ex["horizon"] == 1)
        & (ex["target_date"] > pd.Timestamp(AS_OF - timedelta(days=28)))
        & (ex["target_date"] <= pd.Timestamp(AS_OF - timedelta(days=1)))
        & (ex["t_in_season"] == 1)
    ].copy()

    def likely(frame: pd.DataFrame) -> pd.Series:
        return _predict_frame(forecaster.model, frame, forecaster.cfg, forecaster.shift)["likely"]

    dry = likely(rows).to_numpy()
    wet_rows = rows.copy()
    wet_rows["t_heavy_rain"] = 1
    wet_rows["t_rainfall_mm"] = ex.loc[ex["t_heavy_rain"] == 1, "t_rainfall_mm"].median()
    wet = likely(wet_rows).to_numpy()
    dark = rows["store_id"].astype(str).str.startswith("D").to_numpy()

    walk_in_ratio = wet[~dark].sum() / dry[~dark].sum()
    dark_ratio = wet[dark].sum() / dry[dark].sum()
    assert walk_in_ratio < 0.97, walk_in_ratio  # the data shows about 0.89 for walk-in stores
    assert dark_ratio >= 1.0, dark_ratio  # and about 1.05 for dark stores
