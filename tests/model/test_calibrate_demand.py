from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from harabhara.features.build import CATEGORICAL
from harabhara.models.calibrate import apply_shift, conformal_shift, coverage
from harabhara.models.demand import DemandModel
from harabhara.settings import load_config

SMALL = load_config().modeling.demand.model_copy(update={"iterations": 60, "depth": 3})


def _outcomes(n: int = 4000, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    centre = rng.uniform(20, 100, n)
    actual = pd.Series(centre * rng.lognormal(0, 0.3, n))
    forecast = pd.DataFrame(
        {"low": centre * 0.95, "likely": centre, "high": centre * 1.05}
    )  # far too narrow on purpose
    return forecast, actual


def test_a_narrow_range_is_widened_to_hit_the_target_coverage() -> None:
    forecast, actual = _outcomes()
    before = coverage(forecast, actual)
    shift = conformal_shift(forecast["low"], forecast["high"], actual, coverage=0.8)
    after = coverage(apply_shift(forecast, shift), actual)
    assert before < 0.4
    assert shift > 0
    assert after == pytest.approx(0.8, abs=0.03)


def test_coverage_holds_on_fresh_data_from_the_same_process() -> None:
    forecast, actual = _outcomes(seed=1)
    shift = conformal_shift(forecast["low"], forecast["high"], actual, coverage=0.8)
    fresh_forecast, fresh_actual = _outcomes(seed=2)
    assert coverage(apply_shift(fresh_forecast, shift), fresh_actual) == pytest.approx(
        0.8, abs=0.04
    )


def test_an_over_wide_range_is_tightened() -> None:
    forecast, actual = _outcomes()
    wide = forecast.assign(low=forecast["likely"] * 0.1, high=forecast["likely"] * 5)
    shift = conformal_shift(wide["low"], wide["high"], actual, coverage=0.8)
    assert shift < 0


def test_the_shifted_range_stays_ordered_and_non_negative() -> None:
    forecast, _ = _outcomes()
    for shift in (-500.0, -3.0, 0.0, 3.0, 500.0):
        adjusted = apply_shift(forecast, shift)
        assert (adjusted["low"] >= 0).all()
        assert (adjusted["low"] <= adjusted["likely"] + 1e-9).all()
        assert (adjusted["likely"] <= adjusted["high"] + 1e-9).all()


def test_calibrating_on_nothing_is_an_error() -> None:
    empty = pd.Series([], dtype=float)
    with pytest.raises(ValueError, match="empty"):
        conformal_shift(empty, empty, empty, coverage=0.8)


def _examples(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "store_id": rng.choice(["S01", "D01"], n),
            "sku_id": rng.choice(["P01", "P13"], n),
            "category": "Vegetables",
            "format": rng.choice(["Store", "Dark store"], n),
            "horizon": rng.integers(1, 4, n),
            "demand_mean_7": rng.uniform(20, 100, n),
            "t_is_weekend": rng.integers(0, 2, n),
        }
    )
    frame["y_demand"] = frame["demand_mean_7"] * (1 + 0.3 * frame["t_is_weekend"]) + rng.normal(
        0, 3, n
    )
    return frame


def test_the_model_orders_its_three_outputs_and_learns_the_weekend() -> None:
    examples = _examples()
    columns = [
        "store_id",
        "sku_id",
        "category",
        "format",
        "horizon",
        "demand_mean_7",
        "t_is_weekend",
    ]
    assert set(CATEGORICAL) >= {"store_id", "sku_id", "category", "format"}
    model = DemandModel(SMALL).fit(examples, columns)
    forecast = model.predict(examples)
    assert (forecast["low"] <= forecast["likely"]).all()
    assert (forecast["likely"] <= forecast["high"]).all()
    assert (forecast >= 0).all().all()
    weekend = forecast.loc[examples["t_is_weekend"] == 1, "likely"].mean()
    weekday = forecast.loc[examples["t_is_weekend"] == 0, "likely"].mean()
    assert weekend > weekday
    assert model.importance().index[0] == "demand_mean_7"


def test_predicting_before_fitting_is_an_error() -> None:
    with pytest.raises(RuntimeError, match="not fitted"):
        DemandModel(SMALL).predict(_examples(5))
