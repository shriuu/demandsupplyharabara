"""Unit economics behind the order rule (CLAUDE.md s3).

profit = margin on what sells - cost of produce wasted - cost of sales lost to empty shelves.
A lost sale costs its margin plus an allowance for the rest of the basket (an owner decision,
``config/costs.yaml``; unset means zero and the suggestion says so). A leftover unit costs its
purchase cost, weighted down for products with several sellable days left.
"""

from __future__ import annotations

import pandas as pd


def unit_costs(purchases: pd.DataFrame) -> pd.Series:
    """Quantity-weighted average purchase price per product, in rupees per selling unit."""
    value = purchases["quantity_units"] * purchases["price_per_unit_inr"]
    grouped = pd.DataFrame(
        {"value": value, "qty": purchases["quantity_units"], "sku": purchases["sku_id"]}
    )
    totals = grouped.groupby("sku")[["value", "qty"]].sum()
    costs: pd.Series = (totals["value"] / totals["qty"]).rename("unit_cost")
    return costs


def lost_sale_cost(price: float, cost: float, allowance: float | None) -> float:
    """Margin of the missed sale plus the basket allowance (zero while the owner has not set it)."""
    return max(price - cost, 0.0) + (allowance or 0.0)


def leftover_cost(cost: float, life_days: int, exponent: float) -> float:
    """Cost of one unit left over, lower for products that can still sell tomorrow."""
    return float(cost / (max(life_days, 1) ** exponent))


def critical_ratio(lost_sale: float, leftover: float) -> float:
    """Share of demand scenarios the order should cover so the next unit breaks even."""
    total = lost_sale + leftover
    return float(lost_sale / total) if total > 0 else 0.5
