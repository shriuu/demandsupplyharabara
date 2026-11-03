"""Metric definitions from the playbook (s11) and brief (s7). Pure functions, no I/O."""

from __future__ import annotations

import pandas as pd


def wape(forecast: pd.Series, actual: pd.Series) -> float:
    """Sum |forecast - actual| / sum actual."""
    return float((forecast - actual).abs().sum() / actual.sum())


def bias(forecast: pd.Series, actual: pd.Series) -> float:
    """Sum (forecast - actual) / sum actual; positive means over-forecasting."""
    return float((forecast - actual).sum() / actual.sum())


def wastage_rate(df: pd.DataFrame) -> float:
    """Units binned / units received."""
    return float(df["wastage_units"].sum() / df["received_units"].sum())


def stockout_rate(df: pd.DataFrame) -> float:
    """Share of in-season store-product-days that sold out before closing."""
    return float(df.loc[df["in_season"], "stockout_flag"].mean())


def gross_margin(revenue: float, cost_of_received: float) -> float:
    """(Sales revenue - cost of produce received) / sales revenue."""
    return (revenue - cost_of_received) / revenue
