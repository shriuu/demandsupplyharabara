"""The managers' rule, rebuilt from the playbook, and a same-weekday baseline.

Both use only information available the evening before the target day.
"""

from __future__ import annotations

import pandas as pd

GROUP = ["store_id", "sku_id"]


def seven_day_average(df: pd.DataFrame, window: int, value: str = "sold") -> pd.Series:
    """Mean of the last ``window`` days' sales for the same store and product (excl. today).

    This is the managers' implied forecast (brief s2): the last seven days' average.
    ``df`` must be sorted by date within each store and product.
    """
    return df.groupby(GROUP)[value].transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).mean()
    )


def same_day_last_week(df: pd.DataFrame, value: str = "sold") -> pd.Series:
    """Sales seven days earlier for the same store and product."""
    return df.groupby(GROUP)[value].shift(7)
