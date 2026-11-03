"""Interfaces other workstreams implement. This service defines them and ships fakes only.

* ``PricePort`` is the live mandi-price feed (the feeds workstream).
* ``AssistantPort`` is the chat assistant (the assistant workstream). It rewords one stored
  suggestion; it cannot create or change anything.
"""

from __future__ import annotations

from typing import Protocol

from harabhara.contracts import PriceQuote, Suggestion

NO_ANSWER = "I don't have that."


class PortUnavailableError(Exception):
    """The feed or the assistant is not reachable or not configured."""


class PricePort(Protocol):
    def fetch(self, sku_id: str | None = None) -> list[PriceQuote]:
        """Current public quotes with citations. Raise PortUnavailableError when down."""
        ...


class AssistantPort(Protocol):
    def answer(self, suggestion: Suggestion, question: str) -> str:
        """Answer only from the suggestion's reason and drivers; unknown -> ``NO_ANSWER``."""
        ...


class NotConfiguredPrices:
    """Used until the feed is wired in: the API serves stored prices as stale, or nothing."""

    def fetch(self, sku_id: str | None = None) -> list[PriceQuote]:
        raise PortUnavailableError("price feed not configured")


class NotConfiguredAssistant:
    def answer(self, suggestion: Suggestion, question: str) -> str:
        raise PortUnavailableError("assistant not configured")


class FakePrices:
    def __init__(self, quotes: list[PriceQuote] | None = None, *, down: bool = False) -> None:
        self.quotes = quotes or []
        self.down = down

    def fetch(self, sku_id: str | None = None) -> list[PriceQuote]:
        if self.down:
            raise PortUnavailableError("down")
        return [q for q in self.quotes if sku_id in (None, q.sku_id)]


class FakeAssistant:
    """Echoes the stored reason, which is all the real assistant is allowed to reword."""

    def __init__(self, *, down: bool = False) -> None:
        self.down = down
        self.calls: list[tuple[str, str]] = []

    def answer(self, suggestion: Suggestion, question: str) -> str:
        if self.down:
            raise PortUnavailableError("down")
        self.calls.append((suggestion.id, question))
        return suggestion.reason
