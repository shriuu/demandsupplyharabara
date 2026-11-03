from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from harabhara.data.prepare import build_panel
from harabhara.settings import load_config
from harabhara.sim.simulator import reproduction_report, simulate_history

ROOT = Path(__file__).resolve().parents[2]
SALES = ROOT / "work" / "PS-10_store_sales_daily.xlsx"
EXTERNAL = ROOT / "work" / "PS-10_external_factors.xlsx"
PROC = ROOT / "work" / "PS-10_procurement_and_inventory.xlsx"


def _panel(days: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=days)
    return pd.DataFrame(
        {
            "store_id": "S01",
            "sku_id": "P13",
            "date": dates,
            "in_season": True,
            "demand": [50.0] * days,
            "received_units": [60.0] * days,
        }
    )


def test_every_unit_delivered_is_sold_binned_or_still_on_the_shelf() -> None:
    panel = _panel()
    sim = simulate_history(panel, {"P13": 2}, "freshest_first")
    delivered = panel["received_units"].sum()
    accounted = sim["sim_sold"].sum() + sim["sim_binned"].sum() + sim["sim_closing"].iloc[-1]
    assert accounted == pytest.approx(delivered)


def test_two_day_stock_that_is_overdelivered_is_binned() -> None:
    sim = simulate_history(_panel(), {"P13": 2}, "freshest_first")
    assert sim["sim_binned"].sum() > 0
    assert (sim["sim_lost"] == 0).all()


def test_under_delivery_creates_lost_sales_and_no_waste() -> None:
    panel = _panel()
    panel["received_units"] = 30.0
    sim = simulate_history(panel, {"P13": 2}, "freshest_first")
    assert sim["sim_binned"].sum() == 0
    assert (sim["sim_lost"] > 0).all()


def test_counterfactual_deliveries_replace_the_recorded_ones() -> None:
    panel = _panel()
    more = pd.Series(80.0, index=panel.index)
    base = simulate_history(panel, {"P13": 2}, "freshest_first")
    alt = simulate_history(panel, {"P13": 2}, "freshest_first", deliveries=more)
    assert alt["sim_binned"].sum() > base["sim_binned"].sum()


def test_out_of_season_days_have_no_demand() -> None:
    panel = _panel()
    panel["in_season"] = False
    panel["received_units"] = 0.0
    sim = simulate_history(panel, {"P13": 2}, "freshest_first")
    assert sim[["sim_sold", "sim_lost", "sim_binned"]].to_numpy().sum() == 0


@pytest.mark.skipif(not SALES.exists(), reason="data pack is not in the repository")
def test_fed_the_real_deliveries_the_simulator_reproduces_real_waste() -> None:
    """CLAUDE.md s10: prove the simulator before trusting any replay."""
    cfg = load_config()
    panel, _ = build_panel(SALES, EXTERNAL, cfg)
    panel = panel[panel["split"] == "train"].reset_index(drop=True)
    rules = pd.read_excel(PROC, sheet_name="shelf_life_rules").set_index("sku_id")
    life = {str(k): int(v) for k, v in rules["shelf_life_days_grade_A_ambient"].items()}
    sim = simulate_history(panel, life, cfg.modeling.projection.sales_order)
    report = reproduction_report(sim)
    assert report["sim_waste_rate"] == pytest.approx(report["actual_waste_rate"], abs=0.005)
    assert report["daily_waste_correlation"] > 0.6
    rows = sim[sim["usable_for_targets"]]
    for category, group in rows.groupby("category"):
        actual = group["wastage_units"].sum() / group["received_units"].sum()
        simulated = group["sim_binned"].sum() / group["received_units"].sum()
        assert simulated == pytest.approx(actual, abs=0.01), category
    assert np.isfinite(report["sim_stockout_rate"])
