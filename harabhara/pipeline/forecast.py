"""Fit the demand model on data before the as-of day, calibrate its range, and predict.

Nothing dated after ``fit_until`` is used as a label. The range is calibrated on the four weeks
before ``fit_until`` using a model fit before that window, so the calibration is honest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from harabhara.contracts import Forecast, Range
from harabhara.features.build import feature_columns
from harabhara.models.calibrate import apply_shift, conformal_shift
from harabhara.models.cold_start import apply_thin_history
from harabhara.models.demand import DemandModel
from harabhara.pipeline.inputs import PackData
from harabhara.settings.schema import AppConfig


@dataclass(frozen=True)
class Forecaster:
    model: DemandModel
    shift: float
    cfg: AppConfig
    columns: list[str]
    model_version: str


def _usable(examples: pd.DataFrame) -> pd.Series:
    return (
        (examples["t_usable"] == 1)
        & (examples["t_in_season"] == 1)
        & examples["y_demand"].notna()
        & (examples["t_split"] == "train")
    )


def _predict_frame(
    model: DemandModel, rows: pd.DataFrame, cfg: AppConfig, shift: float
) -> pd.DataFrame:
    """Forecast ranges for ``rows``, with the cold-start rule and the calibrated range."""
    p = cfg.modeling.demand
    raw = model.predict(rows)
    adjusted = apply_thin_history(
        raw, rows, p.min_history_days, p.thin_history_range_width, model.unseen(rows)
    )
    steady = ~adjusted["thin_history"]
    calibrated = adjusted.copy()
    calibrated.loc[steady, ["low", "likely", "high"]] = apply_shift(
        adjusted.loc[steady, ["low", "likely", "high"]], shift
    )
    return calibrated


def fit_forecaster(pack: PackData, fit_until: date) -> Forecaster:
    cfg = pack.cfg
    p, days = cfg.modeling.demand, cfg.modeling.pipeline.calibration_days
    examples = pack.examples
    columns = feature_columns(examples)
    usable = _usable(examples)
    cal_start = pd.Timestamp(fit_until - timedelta(days=days))
    end = pd.Timestamp(fit_until)

    early = DemandModel(p).fit(examples[usable & (examples["target_date"] <= cal_start)], columns)
    window = examples[
        usable
        & (examples["target_date"] > cal_start)
        & (examples["target_date"] <= end)
        & (examples["horizon"] == 1)
    ]
    scored = _predict_frame(early, window, cfg, shift=0.0)
    steady = window[~scored["thin_history"]]
    steady_scores = scored.loc[~scored["thin_history"]]
    shift = conformal_shift(
        steady_scores["low"],
        steady_scores["high"],
        steady["y_demand"],
        coverage=p.quantiles[2] - p.quantiles[0],
    )

    final = DemandModel(p).fit(examples[usable & (examples["target_date"] <= end)], columns)
    return Forecaster(
        model=final, shift=shift, cfg=cfg, columns=columns,
        model_version=f"catboost-demand-fit-to-{fit_until}",
    )  # fmt: skip


def predict_origin(fc: Forecaster, pack: PackData, origin: date) -> pd.DataFrame:
    """Forecasts made on the evening of ``origin`` for the next three days, one row per series.

    The returned frame keeps the example's features (weather, calendar, recent sales) beside
    ``low``, ``likely``, ``high`` and the ``thin_history`` and ``no_history`` flags.
    """
    ex = pack.examples
    rows = ex[(ex["origin"] == pd.Timestamp(origin)) & (ex["t_in_season"] == 1)].copy()
    forecast = _predict_frame(fc.model, rows, fc.cfg, fc.shift)
    out = rows.join(forecast[["low", "likely", "high", "thin_history", "no_history"]])
    out["unseen"] = fc.model.unseen(rows)
    return out.dropna(subset=["likely"])


def to_forecasts(frame: pd.DataFrame, fc: Forecaster, snapshot_id: str) -> list[Forecast]:
    result: list[Forecast] = []
    for row in frame.to_dict("records"):
        flags: list[str] = []
        if row["thin_history"]:
            flags.append("new_product" if row["unseen"] else "new_season")
        result.append(
            Forecast.model_validate(
                {
                    "store_id": row["store_id"],
                    "sku_id": row["sku_id"],
                    "target_date": pd.Timestamp(row["target_date"]).date(),
                    "horizon_days": int(row["horizon"]),
                    "demand": Range(low=row["low"], likely=row["likely"], high=row["high"]),
                    "flags": flags,
                    "demand_estimated": False,
                    "model_version": fc.model_version,
                    "data_snapshot_id": snapshot_id,
                    "config_digest": fc.cfg.digest,
                }
            )
        )
    return result
