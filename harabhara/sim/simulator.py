"""Replay a series' history day by day with the stock ledger (CLAUDE.md s10).

The simulator takes what actually arrived each morning and the demand (sold-out days corrected),
and plays the shelf: shoppers buy the freshest stock first, stock past its last sellable day is
binned at close. Fed the managers' real deliveries it must reproduce their real waste and
stock-outs; only then is a replay with different deliveries worth trusting.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from harabhara.state.projection import Lot, SalesOrder, roll_forward

SERIES = ["store_id", "sku_id"]


def simulate_history(
    panel: pd.DataFrame,
    life_days: Mapping[str, int],
    sales_order: SalesOrder,
    deliveries: pd.Series | None = None,
) -> pd.DataFrame:
    """Add ``sim_sold``, ``sim_lost``, ``sim_binned`` and ``sim_closing`` to every panel row.

    ``life_days`` maps each product to its sellable days at arrival. ``deliveries`` replaces the
    recorded ``received_units`` (same index as ``panel``) for a counterfactual replay.
    """
    received = panel["received_units"] if deliveries is None else deliveries
    out = panel.copy()
    for column in ("sim_sold", "sim_lost", "sim_binned", "sim_closing"):
        out[column] = 0.0
    demand = panel["demand"].where(panel["in_season"], 0.0).fillna(0.0)
    for _, group in panel.groupby(SERIES, sort=False):
        rows = list(group.index)
        life = int(life_days[str(group["sku_id"].iloc[0])])
        arrivals = [
            Lot(float(u), life) if u > 0 else None for u in received.loc[rows].to_numpy(dtype=float)
        ]
        outcomes = roll_forward(
            [], arrivals, demand.loc[rows].to_numpy(dtype=float).tolist(), sales_order
        )
        out.loc[rows, "sim_sold"] = [o.sold for o in outcomes]
        out.loc[rows, "sim_lost"] = [o.lost_sales for o in outcomes]
        out.loc[rows, "sim_binned"] = [o.binned for o in outcomes]
        out.loc[rows, "sim_closing"] = [o.closing_stock for o in outcomes]
    return out


def reproduction_report(sim: pd.DataFrame) -> dict[str, float]:
    """How closely the simulation matches the recorded history on in-season, usable rows."""
    rows = sim[sim["usable_for_targets"]]
    actual_waste = float(rows["wastage_units"].sum() / rows["received_units"].sum())
    sim_waste = float(rows["sim_binned"].sum() / rows["received_units"].sum())
    actual_so = float(rows["stockout_flag"].mean())
    sim_so = float((rows["sim_lost"] > 0).mean())
    corr = float(np.corrcoef(rows["wastage_units"], rows["sim_binned"])[0, 1])
    return {
        "actual_waste_rate": actual_waste,
        "sim_waste_rate": sim_waste,
        "actual_stockout_rate": actual_so,
        "sim_stockout_rate": sim_so,
        "daily_waste_correlation": corr,
    }
