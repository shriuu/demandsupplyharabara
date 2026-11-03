"""Fail safe (guardrail 12): when something is stale or down, show less and say so."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from harabhara.contracts import Forecast, PriceQuote

STALE_HEADER = "X-Data-Stale"


@dataclass(frozen=True)
class Served[T]:
    """Data plus whether it is stale. ``stale`` becomes a response header."""

    items: list[T]
    stale: bool = False


def fresh_forecasts(forecasts: list[Forecast], today: date) -> Served[Forecast]:
    """Drop forecasts for days already past; if any were dropped the rest is marked stale."""
    keep = [f for f in forecasts if f.target_date >= today]
    return Served(keep, stale=len(keep) != len(forecasts))


def as_stale(quotes: list[PriceQuote]) -> list[PriceQuote]:
    """Last stored prices when the live feed is down: ok becomes stale, a price is never made up."""
    return [q.model_copy(update={"status": "stale"}) if q.status == "ok" else q for q in quotes]


def attempt[T](read: Callable[[], list[T]]) -> Served[T]:
    """Run a read; on any failure return nothing, marked stale, so the usual process carries on."""
    try:
        return Served(read())
    except Exception:
        return Served([], stale=True)
