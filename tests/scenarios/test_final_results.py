"""T01, T03, T10: the committed holdout results (docs/final_results.md) say what we claim.

The holdout is read once by scripts/holdout_run.py. These tests read the file it wrote, so they
fail if someone edits the numbers by hand into something that no longer holds.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEXT = (Path(__file__).resolve().parents[2] / "docs" / "final_results.md").read_text(
    encoding="utf-8"
)


def _row(label: str) -> list[float]:
    line = next(ln for ln in TEXT.splitlines() if ln.startswith(f"| {label}"))
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?=%)", line)]


def test_t01_the_model_beats_the_managers_rule_overall() -> None:
    model, managers = _row("Model |")[0], _row("Managers' rule")[0]
    assert model < managers


def test_t01_the_stated_range_holds_close_to_its_share() -> None:
    inside = float(re.search(r"inside the stated range: (\d+\.\d+)%", TEXT).group(1))  # type: ignore[union-attr]
    assert 75.0 <= inside <= 90.0  # an 80% range


def test_t03_festival_eves_lift_bananas_and_coconut_but_leave_onions_alone() -> None:
    uplift = {
        m.group(1): (float(m.group(2)), float(m.group(3)))
        for m in re.finditer(r"\| (P\d\d) \| (\d+\.\d+)x \| (\d+\.\d+)x \|", TEXT)
    }
    for sku in ("P04", "P05", "P12"):  # bananas and tender coconut
        assert uplift[sku][1] >= 1.2  # the data shows a clear lift
        assert uplift[sku][0] > uplift["P02"][0]  # and we forecast more lift than for onion
    assert uplift["P02"][0] < 1.10  # onions almost unchanged


def test_t10_waste_and_empty_shelves_both_fall_with_farmer_volume_intact() -> None:
    managers = _row("Managers' split")
    ours = _row("Our split")
    assert ours[0] < managers[0]  # waste
    assert ours[1] <= managers[1]  # empty shelves do not rise
    assert "sku-days delivered below it: 0 (must be 0)" in TEXT


@pytest.mark.parametrize("measure", ["Waste", "Empty shelves", "Gross margin"])
def test_t10_reports_the_measures_together(measure: str) -> None:
    assert measure in TEXT.split("## T10")[1].split("\n")[1]
