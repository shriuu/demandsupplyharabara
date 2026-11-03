"""Brief T08: 60 kg of grade-B tomatoes in surplus at a store tonight.

Expected: a pickup plan with suitable buyers inside their notice period and pickup window, with
expected recovery in rupees.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from harabhara.decisions.surplus import buyers_from_frame, plan_surplus

PACK = Path(__file__).resolve().parents[2] / "work" / "PS-10_procurement_and_inventory.xlsx"


@pytest.mark.skipif(not PACK.exists(), reason="data pack is not in the repository")
@pytest.mark.parametrize("store", ["S02", "S03", "S08"])
def test_t08_grade_b_tomato_pickup_plan(store: str) -> None:
    buyers = buyers_from_frame(pd.read_excel(PACK, sheet_name="surplus_buyers"))
    now = datetime(2026, 11, 3, 14, 0, tzinfo=UTC)  # the store confirms the plan by 2 pm
    plan = plan_surplus(
        store_id=store, sku_id="P01", grade="B", units=60.0, retail_price=41.0,
        now=now, buyers=buyers, used_capacity={}, horizon_hours=36,
    )  # fmt: skip
    assert plan.matches, "a tomato surplus at this store should find a buyer"
    by_id = {b.buyer_id: b for b in buyers}
    for match in plan.matches:
        buyer = by_id[match.buyer_id]
        assert match.pickup_start >= now + timedelta(hours=buyer.notice_hours)  # notice respected
        assert buyer.window_start <= match.pickup_start.time() <= buyer.window_end
        assert "P01" in buyer.skus
        assert "B" in buyer.grades
        assert buyer.nearest_store == store
        assert match.units <= buyer.max_units
        assert match.expected_recovery_inr >= 0
    assert sum(m.units for m in plan.matches) + plan.unplaced_units == pytest.approx(60.0)
    assert sum(m.expected_recovery_inr for m in plan.matches) > 0
