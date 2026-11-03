"""The rule-to-code-to-test matrix (``docs/traceability.yaml``).

Every playbook rule, guardrail and acceptance scenario has an ID. The matrix says which config
keys it reads, which module enforces it and which test proves it. ``tests/test_traceability.py``
fails if the matrix and the repository drift apart.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: Literal["guardrail", "playbook", "acceptance"]
    source: str
    statement: str
    config_keys: list[str] = Field(default_factory=list)
    enforced_by: str
    test: str
    status: Literal["planned", "implemented", "verified"]


class Matrix(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    items: list[Item]


def default_matrix_path() -> Path:
    return Path(__file__).resolve().parents[1] / "docs" / "traceability.yaml"


def load_matrix(path: Path | None = None) -> Matrix:
    data = yaml.safe_load((path or default_matrix_path()).read_text(encoding="utf-8"))
    return Matrix.model_validate(data)
