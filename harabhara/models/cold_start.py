"""Explicit cold-start handling (brief s5: seasonal products have no history at season start).

A series with too little recent history is not forecast by the global model, which has nothing
to go on for it. The managers-style recent average takes over, the range is a fixed share either
side of it, and the forecast is flagged ``thin_history`` so the screen says so (guardrail G10).
With no history at all there is no forecast, and the flag says that too.
"""

from __future__ import annotations

import pandas as pd


def apply_thin_history(
    forecast: pd.DataFrame,
    examples: pd.DataFrame,
    min_history_days: int,
    range_width: float,
    unseen: pd.Series | None = None,
) -> pd.DataFrame:
    """Replace the model's forecast on thin-history rows with the recent-average fallback.

    ``unseen`` marks products the model never trained on; they always use the fallback, because
    the model has nothing to say about them however much recent history they have.
    """
    thin = examples["history_days"] < min_history_days
    if unseen is not None:
        thin = thin | unseen
    fallback = examples["sold_mean_7"]
    out = forecast.copy()
    out.loc[thin, "likely"] = fallback[thin]
    out.loc[thin, "low"] = fallback[thin] * (1 - range_width)
    out.loc[thin, "high"] = fallback[thin] * (1 + range_width)
    out["thin_history"] = thin
    out["no_history"] = thin & fallback.isna()
    return out
