"""Point-in-time features for the demand forecast (CLAUDE.md s10 step 4).

One example is a store-product forecast made on the evening of an *origin* day for a *target*
day one to three days ahead. Every feature uses only what is known at the origin:
- demand history up to and including the origin (sold-out days corrected, S07 outage rebuilt),
- the calendar and weather of the target day (the calendar is known in advance; weather stands in
  for a forecast, see ``config/modeling.yaml``),
- shelf price and mandi price at the origin.
``tests/model/test_features_point_in_time.py`` fails if any feature depends on data after the
origin.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from harabhara.settings.schema import DemandParams

SERIES = ["store_id", "sku_id"]

CATEGORICAL = ["store_id", "sku_id", "category", "format"]
NUMERIC_STATIC = ["size_index", "chilled_display", "festival_sensitive"]
TARGETS = [
    "y_demand",
    "y_sold",
    "t_demand_estimated",
    "t_stockout",
    "t_usable",
    "t_in_season",
    "t_split",
]


def assemble_panel(
    demand: pd.DataFrame,
    stores: pd.DataFrame,
    skus: pd.DataFrame,
    calendar: pd.DataFrame,
    weather: pd.DataFrame,
    mandi: pd.DataFrame,
) -> pd.DataFrame:
    """One row per store, product and date with everything the examples are built from.

    ``demand`` is cleaned sales after the hidden-demand step (needs ``demand``,
    ``demand_estimated``, ``sold``, ``usable_for_targets``, ``in_season``, ``stockout_flag``).
    """
    store_columns = ["store_id", "format", "size_index", "chilled_display"]
    keep = ["store_id", *[c for c in store_columns[1:] if c not in demand.columns]]
    panel = demand.merge(stores[keep], on="store_id") if len(keep) > 1 else demand.copy()
    panel = panel.merge(skus[["sku_id", "category", "festival_sensitive"]], on="sku_id")
    cal = calendar.rename(columns={"festival_intensity": "festival_intensity_day"})
    panel = panel.merge(
        cal[
            [
                "date",
                "weekday",
                "is_weekend",
                "festival_intensity_day",
                "is_month_start_payday",
                "school_holiday",
            ]
        ],
        on="date",
    )
    panel = panel.merge(
        weather[
            ["date", "max_temp_c", "min_temp_c", "rainfall_mm", "humidity_pct", "heavy_rain_flag"]
        ],
        on="date",
    )
    panel = panel.merge(
        mandi[["date", "sku_id", "modal_price_inr", "arrivals_tonnes"]],
        on=["date", "sku_id"],
        how="left",
    )
    panel = panel.sort_values([*SERIES, "date"]).reset_index(drop=True)
    for column in ("chilled_display", "festival_sensitive", "is_weekend", "is_month_start_payday"):
        panel[column] = panel[column].astype(int)
    panel["school_holiday"] = panel["school_holiday"].astype(int)
    panel["heavy_rain_flag"] = panel["heavy_rain_flag"].astype(int)
    panel["dow"] = panel["date"].dt.dayofweek
    panel["day_of_month"] = panel["date"].dt.day
    return panel


def _origin_features(panel: pd.DataFrame, params: DemandParams) -> pd.DataFrame:
    """Features at each origin day, using data up to and including that day."""
    out = pd.DataFrame({k: panel[k] for k in (*SERIES, "date")})
    in_season = panel["in_season"]
    demand = panel["demand"].where(in_season)
    sold = panel["sold"].where(in_season)
    grouped_d = demand.groupby([panel[k] for k in SERIES])
    grouped_s = sold.groupby([panel[k] for k in SERIES])

    for lag in range(3):
        out[f"demand_lag_{lag}"] = grouped_d.shift(lag)
    for window in params.rolling_windows:
        out[f"demand_mean_{window}"] = grouped_d.transform(
            lambda s, w=window: s.rolling(w, min_periods=1).mean()
        )
    out["demand_std_28"] = grouped_d.transform(lambda s: s.rolling(28, min_periods=2).std())
    out["history_days"] = grouped_d.transform(
        lambda s: s.notna().rolling(params.history_window_days, min_periods=1).sum()
    )
    # What the managers' rule sees: units sold, not corrected demand.
    out["sold_mean_7"] = grouped_s.transform(lambda s: s.rolling(7, min_periods=1).mean())

    stockout = panel["stockout_flag"].astype(float).where(in_season)
    out["stockout_share_recent"] = stockout.groupby([panel[k] for k in SERIES]).transform(
        lambda s: s.rolling(params.stockout_window_days, min_periods=1).mean()
    )
    out["stocked_out_at_origin"] = stockout.fillna(0.0)

    season_break = (~in_season).astype(int).groupby([panel[k] for k in SERIES]).cumsum()
    out["days_in_season"] = (
        in_season.astype(int).groupby([panel[k] for k in SERIES] + [season_break]).cumsum()
    )
    out.loc[~in_season, "days_in_season"] = 0

    price = panel["selling_price"].astype(float)
    price_mean = price.groupby([panel[k] for k in SERIES]).transform(
        lambda s: s.rolling(params.price_window_days, min_periods=1).mean()
    )
    out["shelf_price"] = price
    out["price_vs_recent"] = price / price_mean
    out["promo_at_origin"] = panel["promo_flag"].astype(int)
    out["mandi_modal_price"] = panel["modal_price_inr"]
    out["mandi_arrivals"] = panel["arrivals_tonnes"]
    return out


def make_examples(panel: pd.DataFrame, params: DemandParams, horizons: int) -> pd.DataFrame:
    """Build one example per store, product, origin and horizon (1 to ``horizons`` days)."""
    origin = _origin_features(panel, params)
    keys = [panel[k] for k in SERIES]
    grouped_demand = panel["demand"].where(panel["in_season"]).groupby(keys)
    intensity = panel["festival_intensity_day"].groupby(keys)

    frames: list[pd.DataFrame] = []
    for h in range(1, horizons + 1):
        frame = origin.copy()
        frame = frame.rename(columns={"date": "origin"})
        frame["horizon"] = h
        frame["target_date"] = frame["origin"] + pd.Timedelta(days=h)

        for week in params.same_weekday_lags:
            frame[f"demand_same_weekday_{week}w"] = grouped_demand.shift(7 * week - h)

        def at_target(column: pd.Series, steps: int = h) -> pd.Series:
            return column.groupby(keys).shift(-steps)

        frame["t_dow"] = at_target(panel["dow"])
        frame["t_is_weekend"] = at_target(panel["is_weekend"])
        frame["t_day_of_month"] = at_target(panel["day_of_month"])
        frame["t_payday"] = at_target(panel["is_month_start_payday"])
        frame["t_school_holiday"] = at_target(panel["school_holiday"])
        frame["t_festival_intensity"] = at_target(panel["festival_intensity_day"])
        frame["t_eve_intensity"] = intensity.shift(-(h + 1))
        frame["t_after_intensity"] = (
            intensity.shift(-(h - 1)) if h > 1 else panel["festival_intensity_day"]
        )
        frame["t_max_temp_c"] = at_target(panel["max_temp_c"])
        frame["t_min_temp_c"] = at_target(panel["min_temp_c"])
        frame["t_rainfall_mm"] = at_target(panel["rainfall_mm"])
        frame["t_humidity_pct"] = at_target(panel["humidity_pct"])
        frame["t_heavy_rain"] = at_target(panel["heavy_rain_flag"])

        frame["y_demand"] = at_target(panel["demand"])
        frame["y_sold"] = at_target(panel["sold"])
        frame["t_demand_estimated"] = at_target(panel["demand_estimated"].astype(float))
        frame["t_stockout"] = at_target(panel["stockout_flag"].astype(float))
        frame["t_usable"] = at_target(panel["usable_for_targets"].astype(float))
        frame["t_in_season"] = at_target(panel["in_season"].astype(float))
        frame["t_split"] = at_target(panel["split"])

        for column in (*CATEGORICAL, *NUMERIC_STATIC):
            frame[column] = panel[column].to_numpy() if column in panel else np.nan
        frames.append(frame)

    examples = pd.concat(frames, ignore_index=True)
    return examples.dropna(subset=["t_in_season"]).reset_index(drop=True)


def feature_columns(examples: pd.DataFrame) -> list[str]:
    """Columns the model may see: everything except keys, targets and target-day flags."""
    excluded = {*TARGETS, "origin", "target_date"}
    return [c for c in examples.columns if c not in excluded]
