"""Split a fixed supply across stores (the committed purchase is never reduced here).

Units are handed out one step at a time to the store where the next unit is worth most:
value = (lost-sale cost) x P(demand above what the store would then hold)
        - (leftover cost) x P(demand at or below it).
So the pool goes where a shop is most likely to run out, and stays away from shops that already
hold enough. With ``force_all`` every unit is placed (the supply is committed); without it,
units whose next value is not positive are held back as surplus for transfer or buyers.
"""

from __future__ import annotations

import heapq
from collections.abc import Sequence
from dataclasses import dataclass

from harabhara.contracts import Range
from harabhara.decisions.order import Quantiles, cdf


@dataclass(frozen=True)
class StoreNeed:
    store_id: str
    demand: Range
    stock: float  # sellable stock already on the shelf tomorrow
    lost_sale_cost: float
    leftover_cost: float


@dataclass(frozen=True)
class Allocation:
    units: dict[str, float]
    held_back: float  # supply left unplaced (only when force_all is False)


def _value(need: StoreNeed, held: float, quantiles: Quantiles) -> float:
    p_short = 1 - cdf(need.demand, held, quantiles)
    return need.lost_sale_cost * p_short - need.leftover_cost * (1 - p_short)


def allocate(
    pool: float,
    needs: Sequence[StoreNeed],
    quantiles: Quantiles,
    steps: int,
    force_all: bool = True,
) -> Allocation:
    if pool < 0:
        msg = "supply cannot be negative"
        raise ValueError(msg)
    units = {n.store_id: 0.0 for n in needs}
    if pool == 0 or not needs:
        return Allocation(units=units, held_back=max(pool, 0.0))
    step = max(pool / steps, 1e-6)
    remaining = pool
    by_id = {n.store_id: n for n in needs}
    heap = [(-_value(n, n.stock, quantiles), n.store_id) for n in needs]
    heapq.heapify(heap)
    while remaining > 1e-9:
        negative_value, store = heap[0]
        if -negative_value <= 0 and not force_all:
            break
        give = min(step, remaining)
        units[store] += give
        remaining -= give
        need = by_id[store]
        heapq.heapreplace(heap, (-_value(need, need.stock + units[store], quantiles), store))
    return Allocation(units=units, held_back=remaining)
