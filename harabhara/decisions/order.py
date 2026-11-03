"""Order ask: the quantity a store needs, sized to demand and what it already holds.

The forecast gives three points of the demand distribution (low, likely, high at the 10th, 50th
and 90th percentile). The order covers demand up to the point where one more unit would cost
more in expected waste than it earns in expected sales (``economics.critical_ratio``), less the
stock the store will still be able to sell. There is no flat safety cushion: the cushion is the
range, so a sell-out yesterday does not inflate tomorrow's order (CLAUDE.md s3, way 2).
"""

from __future__ import annotations

import math

from harabhara.contracts import Range

Quantiles = tuple[float, float, float]
TAIL_FLOOR = 1e-9


def cdf(demand: Range, x: float, quantiles: Quantiles) -> float:
    """P(demand <= x): linear between the forecast points, an exponential tail beyond the top."""
    p_low, p_mid, p_high = quantiles
    if x <= 0:
        return 0.0
    if x < demand.low:
        return p_low * x / demand.low
    if x < demand.likely:
        span = demand.likely - demand.low
        return p_low if span <= 0 else p_low + (p_mid - p_low) * (x - demand.low) / span
    if x < demand.high:
        span = demand.high - demand.likely
        return p_mid if span <= 0 else p_mid + (p_high - p_mid) * (x - demand.likely) / span
    scale = max(demand.high - demand.likely, TAIL_FLOOR)
    return p_high + (1 - p_high) * (1 - math.exp(-(x - demand.high) / scale))


def quantile_value(demand: Range, q: float, quantiles: Quantiles) -> float:
    """The demand level covered with probability ``q`` (inverse of ``cdf``)."""
    p_low, p_mid, p_high = quantiles
    q = min(max(q, 0.0), 1 - TAIL_FLOOR)
    if q <= p_low:
        return demand.low * q / p_low
    if q <= p_mid:
        return demand.low + (demand.likely - demand.low) * (q - p_low) / (p_mid - p_low)
    if q <= p_high:
        return demand.likely + (demand.high - demand.likely) * (q - p_mid) / (p_high - p_mid)
    scale = max(demand.high - demand.likely, TAIL_FLOOR)
    return demand.high - scale * math.log(1 - (q - p_high) / (1 - p_high))


def order_ask(demand: Range, sellable_stock: float, ratio: float, quantiles: Quantiles) -> float:
    """Units to bring in so demand is covered with probability ``ratio`` given stock on hand."""
    return max(0.0, quantile_value(demand, ratio, quantiles) - max(sellable_stock, 0.0))
