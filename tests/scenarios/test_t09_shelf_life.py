"""Brief test T09: tomato, two days since harvest, received at 31 C, firmness 5.8.

Expected: remaining sellable days below the fixed rule, with a reason (the warm arrival and age).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from harabhara.models.shelf_life import FEATURES, ShelfLifeModel, rule_cap, rule_days
from harabhara.settings import load_config

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "work" / "PS-10_procurement_and_inventory.xlsx"


@pytest.mark.skipif(not PACK.exists(), reason="data pack is not in the repository")
def test_t09_tomato_is_estimated_below_the_fixed_rule() -> None:
    cfg = load_config()
    p = cfg.modeling.shelf_life
    qc = pd.read_excel(PACK, sheet_name="qc_samples")
    rules = pd.read_excel(PACK, sheet_name="shelf_life_rules")
    qc["date"] = pd.to_datetime(qc["date"])
    fit = qc[qc["date"] <= pd.Timestamp(p.fit_until)]
    tomato = fit[fit["sku_id"] == "P01"]
    case = pd.DataFrame(
        [
            {
                "sku_id": "P01",
                "source_type": "Mandi auction",
                "grade_assigned": "B",
                "days_since_harvest": 2,
                "receipt_temperature_c": 31.0,
                "firmness_score_1_10": 5.8,
                "colour_score_1_10": float(tomato["colour_score_1_10"].median()),
                "visible_defects_pct": float(tomato["visible_defects_pct"].median()),
            }
        ]
    )[FEATURES]
    model = ShelfLifeModel(p).fit(fit)
    cap = rule_cap(case, rules, cfg.rules.receiving)
    estimate = model.predict(case, cap)
    fixed = rule_days(case, rules).iloc[0]
    assert estimate.likely.iloc[0] < fixed
    assert estimate.high.iloc[0] <= cap.iloc[0]  # never past the playbook's last sellable day
