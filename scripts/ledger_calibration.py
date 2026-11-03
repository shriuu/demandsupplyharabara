"""Find which arrival-life assumption lets the simulator reproduce the recorded waste.

Uses the training period only. Usage: uv run python scripts/ledger_calibration.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from harabhara.data.prepare import build_panel
from harabhara.settings import load_config
from harabhara.sim.simulator import reproduction_report, simulate_history

ROOT = Path(__file__).resolve().parents[1]
SALES = ROOT / "work" / "PS-10_store_sales_daily.xlsx"
EXTERNAL = ROOT / "work" / "PS-10_external_factors.xlsx"
PROC = ROOT / "work" / "PS-10_procurement_and_inventory.xlsx"


def main() -> None:
    cfg = load_config()
    panel, _ = build_panel(SALES, EXTERNAL, cfg)
    panel = panel[panel["split"] == "train"].reset_index(drop=True)
    rules = pd.read_excel(PROC, sheet_name="shelf_life_rules").set_index("sku_id")
    order = cfg.modeling.projection.sales_order
    options = {
        "grade A rule": rules["shelf_life_days_grade_A_ambient"],
        "grade B rule": rules["shelf_life_days_grade_B_ambient"],
        "grade C rule": rules["shelf_life_days_grade_C_ambient"],
        "grade A rule minus 1": (rules["shelf_life_days_grade_A_ambient"] - 1).clip(lower=1),
        "grade B rule minus 1": (rules["shelf_life_days_grade_B_ambient"] - 1).clip(lower=1),
    }
    print(f"training rows: {len(panel):,}; sales order: {order}\n")
    print(
        "| Arrival life | waste actual | waste sim | stock-outs actual | stock-outs sim | daily waste corr |"
    )
    print("|---|---|---|---|---|---|")
    for name, life in options.items():
        sim = simulate_history(panel, life.astype(int).to_dict(), order)
        r = reproduction_report(sim)
        print(
            f"| {name} | {r['actual_waste_rate']:.2%} | {r['sim_waste_rate']:.2%} | "
            f"{r['actual_stockout_rate']:.2%} | {r['sim_stockout_rate']:.2%} | {r['daily_waste_correlation']:.2f} |"
        )


if __name__ == "__main__":
    main()
