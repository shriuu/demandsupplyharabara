from __future__ import annotations

import re
from pathlib import Path

import pytest

from harabhara.settings import load_config, resolve
from harabhara.traceability import Item, load_matrix

ROOT = Path(__file__).resolve().parents[1]
ITEMS = load_matrix().items

ID_PATTERN = {
    "guardrail": re.compile(r"^G\d{2}$"),
    "playbook": re.compile(r"^PB\d{2}$"),
    "acceptance": re.compile(r"^T\d{2}$"),
}


def test_ids_are_unique() -> None:
    ids = [item.id for item in ITEMS]
    assert len(ids) == len(set(ids))


def test_ids_match_their_kind() -> None:
    for item in ITEMS:
        assert ID_PATTERN[item.kind].match(item.id), item.id


def test_every_guardrail_and_acceptance_scenario_is_present() -> None:
    ids = {item.id for item in ITEMS}
    assert {f"G{n:02d}" for n in range(1, 13)} <= ids  # CLAUDE.md section 5
    assert {f"T{n:02d}" for n in range(1, 11)} <= ids  # brief section 6


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_config_keys_resolve(item: Item) -> None:
    cfg = load_config()
    for key in item.config_keys:
        resolve(cfg, key)  # raises KeyError if the matrix points at a key that does not exist


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_paths_stay_inside_the_repo_layout(item: Item) -> None:
    assert item.enforced_by.startswith("harabhara/")
    assert item.test.startswith("tests/")


@pytest.mark.parametrize("item", [i for i in ITEMS if i.status != "planned"], ids=lambda i: i.id)
def test_non_planned_items_have_code_and_test(item: Item) -> None:
    assert (ROOT / item.enforced_by).is_file()
    assert (ROOT / item.test).is_file()
