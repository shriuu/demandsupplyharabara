"""Load, validate and fingerprint the files in ``config/``."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from harabhara.settings.schema import AppConfig, Costs, Metrics, Rules, Schedule

CONFIG_FILES = ("rules", "schedule", "metrics", "costs")


class PlaceholderError(RuntimeError):
    """Code needed a value that is still an open owner question."""


def default_config_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


def _read(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"{path} must contain a mapping at the top level"
        raise TypeError(msg)
    return data, raw


def load_config(config_dir: Path | None = None) -> AppConfig:
    """Validate all four files and fingerprint them together."""
    directory = config_dir or default_config_dir()
    parsed: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    for name in CONFIG_FILES:
        parsed[name], raw = _read(directory / f"{name}.yaml")
        digest.update(name.encode())
        digest.update(raw)
    return AppConfig(
        rules=Rules.model_validate(parsed["rules"]),
        schedule=Schedule.model_validate(parsed["schedule"]),
        metrics=Metrics.model_validate(parsed["metrics"]),
        costs=Costs.model_validate(parsed["costs"]),
        digest=digest.hexdigest(),
    )


def _walk(node: Any, prefix: str) -> list[tuple[str, Any]]:
    if isinstance(node, dict):
        out: list[tuple[str, Any]] = []
        for key, value in node.items():
            out.extend(_walk(value, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return [(prefix, node)]


def _dump(cfg: AppConfig) -> dict[str, Any]:
    return cfg.model_dump(mode="python", by_alias=False, exclude={"digest"})


def placeholders(cfg: AppConfig) -> list[str]:
    """Dotted paths (``costs.basket_allowance_per_lost_sale_inr``) that are still unset."""
    return sorted(path for path, value in _walk(_dump(cfg), "") if value is None)


def resolve(cfg: AppConfig, dotted: str) -> Any:
    """Look up a dotted config path such as ``rules.markdown.step_1_pct``."""
    node: Any = _dump(cfg)
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            msg = f"config path not found: {dotted}"
            raise KeyError(msg)
        node = node[part]
    return node


def require[T](value: T | None, path: str) -> T:
    """Return ``value`` or fail loudly if it is an unanswered owner question."""
    if value is None:
        msg = f"{path} is not set: it is an open owner question (docs/owner_questions.md)"
        raise PlaceholderError(msg)
    return value
