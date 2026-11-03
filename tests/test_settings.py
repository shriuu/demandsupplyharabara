from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from harabhara.settings import PlaceholderError, load_config, placeholders, require, resolve
from harabhara.settings.loader import CONFIG_FILES, default_config_dir


def test_real_config_loads() -> None:
    cfg = load_config()
    assert cfg.rules.farmers.never_below_floor is True
    assert cfg.rules.automation.auto_order_allowed is False
    assert cfg.rules.ordering.approval_required is True


def test_digest_is_stable_and_changes_with_content(tmp_path: Path) -> None:
    for name in CONFIG_FILES:
        shutil.copy(default_config_dir() / f"{name}.yaml", tmp_path / f"{name}.yaml")
    first = load_config(tmp_path).digest
    assert first == load_config().digest
    costs = tmp_path / "costs.yaml"
    costs.write_text(costs.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    assert load_config(tmp_path).digest != first


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    for name in CONFIG_FILES:
        shutil.copy(default_config_dir() / f"{name}.yaml", tmp_path / f"{name}.yaml")
    path = tmp_path / "rules.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["transfer"]["max_distance"] = 6  # typo of max_distance_km must not pass silently
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(tmp_path)


def test_open_owner_questions_are_listed() -> None:
    open_items = placeholders(load_config())
    assert "costs.basket_allowance_per_lost_sale_inr" in open_items
    assert "metrics.farmer_share" in open_items
    assert "rules.transfer.store_distances" in open_items


def test_require_fails_on_a_placeholder() -> None:
    cfg = load_config()
    with pytest.raises(PlaceholderError, match="owner question"):
        require(cfg.costs.basket_allowance_per_lost_sale_inr, "costs.basket_allowance")
    assert require(cfg.rules.transfer.van_cost_inr, "rules.transfer.van_cost_inr") > 0


def test_resolve_dotted_paths() -> None:
    cfg = load_config()
    assert resolve(cfg, "rules.markdown.step_1_pct") == cfg.rules.markdown.step_1_pct
    with pytest.raises(KeyError):
        resolve(cfg, "rules.markdown.nope")


def test_non_mapping_file_is_rejected(tmp_path: Path) -> None:
    for name in CONFIG_FILES:
        shutil.copy(default_config_dir() / f"{name}.yaml", tmp_path / f"{name}.yaml")
    (tmp_path / "costs.yaml").write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(TypeError, match="mapping"):
        load_config(tmp_path)
