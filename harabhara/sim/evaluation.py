"""Slice reports: forecast miss and bias, overall and by the slices that matter (CLAUDE.md s10)."""

from __future__ import annotations

import pandas as pd

from harabhara.sim.metrics import bias, wape


def score(frame: pd.DataFrame, forecast: str, actual: str) -> dict[str, float]:
    return {
        "n": float(len(frame)),
        "wape": wape(frame[forecast], frame[actual]),
        "bias": bias(frame[forecast], frame[actual]),
    }


def by_slice(
    frame: pd.DataFrame, slice_column: str, forecasts: dict[str, str], actual: str
) -> pd.DataFrame:
    """One row per slice value with WAPE and bias for each named forecast column."""
    rows = []
    for value, group in frame.groupby(slice_column, observed=True):
        row: dict[str, object] = {slice_column: value, "n": len(group)}
        for name, column in forecasts.items():
            result = score(group, column, actual)
            row[f"{name} WAPE"] = result["wape"]
            row[f"{name} bias"] = result["bias"]
        rows.append(row)
    return pd.DataFrame(rows)
