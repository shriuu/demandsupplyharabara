"""Provider-neutral text-completion interface. A provider gets text in and returns text out."""

from __future__ import annotations

from typing import Protocol


class ProviderError(RuntimeError):
    """The provider failed or timed out. The message never contains a key."""


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the model's reply. Raises ``ProviderError`` on any failure."""
        ...
