"""Estimate the demand that sold-out days hid (CLAUDE.md s7 factor 1, s10 step 2).

On a sold-out day, units sold equal the stock, not the demand. If a product sold out at hour h,
demand over the whole day is estimated as ``sold / share_of_day(h)``, where ``share_of_day`` is
the fraction of the trading day gone by hour h, raised to a profile exponent. The data has no
hourly sales, so the profile is an assumption (see ``config/modeling.yaml``).

Rows keep both the observed ``sold_corrected`` and the estimate, plus a flag, so evaluation can
use only honest (non-sold-out) rows as ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from harabhara.settings.schema import HiddenDemandParams, StoreHours


@dataclass(frozen=True)
class Hours:
    open: float
    close: float


def clock_to_hour(clock: str) -> float:
    """'07:30' -> 7.5; '24:00' -> 24.0."""
    hours, minutes = clock.split(":")
    return int(hours) + int(minutes) / 60


def hours_by_format(store_hours: StoreHours) -> dict[str, Hours]:
    return {
        "Store": Hours(
            clock_to_hour(store_hours.Store.open), clock_to_hour(store_hours.Store.close)
        ),
        "Dark store": Hours(
            clock_to_hour(store_hours.Dark_store.open),
            clock_to_hour(store_hours.Dark_store.close),
        ),
    }


def share_of_day(
    sold_out_hour: pd.Series,
    open_hour: pd.Series,
    close_hour: pd.Series,
    params: HiddenDemandParams,
) -> pd.Series:
    """Fraction of the day's demand assumed sold by ``sold_out_hour``, bounded below."""
    elapsed = (sold_out_hour - open_hour) / (close_hour - open_hour)
    elapsed = elapsed.clip(lower=params.min_fraction_of_day, upper=1.0)
    return elapsed**params.intraday_profile_gamma


def estimate_demand(
    df: pd.DataFrame, hours: dict[str, Hours], params: HiddenDemandParams
) -> pd.DataFrame:
    """Add ``demand`` and ``demand_estimated`` to cleaned sales (needs ``format``).

    ``demand`` is ``sold_corrected`` on rows that did not sell out; on sold-out rows it is the
    estimate, never below what was actually sold.
    """
    out = df.copy()
    open_hour = out["format"].map(lambda f: hours[f].open).astype(float)
    close_hour = out["format"].map(lambda f: hours[f].close).astype(float)
    censored = out["stockout_flag"] & out["sold_out_hour"].notna()
    share = share_of_day(out["sold_out_hour"], open_hour, close_hour, params)
    estimate = out["sold_corrected"] / share
    out["demand"] = np.where(
        censored, np.maximum(estimate, out["sold_corrected"]), out["sold_corrected"]
    )
    out["demand_estimated"] = censored
    return out


@dataclass(frozen=True)
class TruncationResult:
    gamma_true: float
    bias: float  # sum (estimate - truth) / sum truth; positive means over-estimating
    wape: float


def validate_by_truncation(
    honest: pd.DataFrame,
    hours: dict[str, Hours],
    params: HiddenDemandParams,
    observed_shares: np.ndarray,
    gamma_true: float,
    seed: int,
) -> TruncationResult:
    """Test the estimator on days where demand is known.

    Takes rows that did not sell out (demand known), cuts their sales at a day-share drawn from
    the real sold-out shares, as if the product had sold out then, and checks how well
    ``estimate_demand`` recovers the truth. ``gamma_true`` is the real intraday pace the
    truncation uses; the estimator still assumes ``params.intraday_profile_gamma``. Running it with
    several ``gamma_true`` shows the damage if the assumed pace is wrong.
    """
    rng = np.random.default_rng(seed)
    shares = rng.choice(observed_shares, size=len(honest))
    truth = honest["sold_corrected"].to_numpy(dtype=float)
    kept = truth * shares**gamma_true  # what would have sold before running out

    open_hour = honest["format"].map(lambda f: hours[f].open).to_numpy(dtype=float)
    close_hour = honest["format"].map(lambda f: hours[f].close).to_numpy(dtype=float)
    hour = open_hour + shares * (close_hour - open_hour)

    trial = honest.copy()
    trial["sold_corrected"] = kept
    trial["stockout_flag"] = True
    trial["sold_out_hour"] = hour
    estimate = estimate_demand(trial, hours, params)["demand"].to_numpy(dtype=float)
    return TruncationResult(
        gamma_true=gamma_true,
        bias=float((estimate - truth).sum() / truth.sum()),
        wape=float(np.abs(estimate - truth).sum() / truth.sum()),
    )
