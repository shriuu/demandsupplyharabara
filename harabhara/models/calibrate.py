"""Make the stated range honest (split conformal adjustment).

A range called "80%" should hold about 80% of outcomes. The raw quantile models rarely do, so we
measure how far outcomes fall outside the range on a calibration window and shift both ends by
the amount that restores the target share. The likely value is left alone.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def conformal_shift(low: pd.Series, high: pd.Series, actual: pd.Series, coverage: float) -> float:
    """How far to move each end outward (negative: inward) to hit ``coverage`` on this window."""
    scores = np.maximum(low.to_numpy() - actual.to_numpy(), actual.to_numpy() - high.to_numpy())
    n = len(scores)
    if n == 0:
        msg = "cannot calibrate on an empty window"
        raise ValueError(msg)
    level = min(1.0, math.ceil((n + 1) * coverage) / n)
    return float(np.quantile(scores, level))


def apply_shift(forecast: pd.DataFrame, shift: float) -> pd.DataFrame:
    """Move the low and high ends by ``shift``, never below zero and never past the likely value."""
    out = forecast.copy()
    out["low"] = np.minimum(np.clip(forecast["low"] - shift, 0, None), forecast["likely"])
    out["high"] = np.maximum(forecast["high"] + shift, forecast["likely"])
    return out


def coverage(forecast: pd.DataFrame, actual: pd.Series) -> float:
    """Share of outcomes inside the low-to-high range."""
    return float(((actual >= forecast["low"]) & (actual <= forecast["high"])).mean())
