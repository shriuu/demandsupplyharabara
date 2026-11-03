"""A tiny stand-in for ``google.cloud.firestore.Client`` (no network, no emulator).

Covers what ``FirestoreStorage`` uses: get/set/create/update with a last-update-time
precondition, equality ``where`` queries and ``stream``.
"""

from __future__ import annotations

import copy
from typing import Any

from google.api_core import exceptions as gexc


class Snap:
    def __init__(self, data: dict[str, Any] | None, version: int) -> None:
        self._data = data
        self.update_time = version

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data or {})


class StreamedDoc:
    def __init__(self, data: dict[str, Any], reference: Doc, doc_id: str) -> None:
        self._data = data
        self.reference = reference
        self.id = doc_id

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)


class Doc:
    def __init__(self, col: Col, doc_id: str) -> None:
        self._col = col
        self._id = doc_id

    def get(self) -> Snap:
        data, version = self._col.rows.get(self._id, (None, 0))
        return Snap(data, version)

    def set(self, data: dict[str, Any]) -> None:
        _, version = self._col.rows.get(self._id, (None, 0))
        self._col.rows[self._id] = (copy.deepcopy(data), version + 1)

    def create(self, data: dict[str, Any]) -> None:
        if self._id in self._col.rows:
            raise gexc.AlreadyExists(self._id)  # type: ignore[no-untyped-call]
        self.set(data)

    def delete(self) -> None:
        self._col.rows.pop(self._id, None)

    def update(self, data: dict[str, Any], option: Any = None) -> None:
        current, version = self._col.rows[self._id]
        if option is not None and option != version:
            raise gexc.FailedPrecondition("changed since read")  # type: ignore[no-untyped-call]
        assert current is not None
        self._col.rows[self._id] = ({**current, **data}, version + 1)


class Col:
    def __init__(self) -> None:
        self.rows: dict[str, tuple[dict[str, Any], int]] = {}
        self._filters: list[tuple[str, Any]] = []

    def document(self, doc_id: str) -> Doc:
        return Doc(self, doc_id)

    def where(self, field: str, op: str, value: Any) -> Col:
        assert op == "=="
        clone = Col()
        clone.rows = self.rows
        clone._filters = [*self._filters, (field, value)]
        return clone

    def stream(self) -> list[Any]:
        out = []
        for doc_id, (data, _) in list(self.rows.items()):
            if all(data.get(f) == v for f, v in self._filters):
                out.append(StreamedDoc(data, Doc(self, doc_id), doc_id))
        return out


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[str, Col] = {}

    def collection(self, name: str) -> Col:
        return self.collections.setdefault(name, Col())

    @staticmethod
    def write_option(last_update_time: int) -> int:
        return last_update_time
