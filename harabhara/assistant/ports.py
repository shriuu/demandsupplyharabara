"""What the assistant needs from the platform.

``harabhara/api/ports.py`` did not exist on ``origin/platform`` when this was written, so these
are this package's own small Protocols. The platform session can satisfy them with a Firestore
reader (role and store scoping is checked by the API before it calls the assistant).
"""

from __future__ import annotations

from typing import Protocol

from harabhara.contracts import Suggestion


class SuggestionReader(Protocol):
    def get_suggestion(self, suggestion_id: str) -> Suggestion | None: ...
