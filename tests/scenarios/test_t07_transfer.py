"""Brief T07: one store holds twice its expected beans demand while a nearby store runs out.

Expected: a transfer with quantity, timing before 11 am and the van cost, for area manager approval.
"""

from __future__ import annotations

from harabhara.decisions.transfer import plan_transfers
from harabhara.settings import load_config

RULES = load_config().rules.transfer


def test_t07_beans_transfer() -> None:
    expected_demand = 40.0
    plans = plan_transfers(
        category="Vegetables",
        now_hour=7.5,
        surplus={
            "S01": expected_demand
        },  # holds twice its expected demand, so one demand's worth is spare
        shortage={"S03": 30.0},
        pairs={("S01", "S03")},
        price={"S01": 81.0, "S03": 81.0},  # beans, typical retail price
        markdown_share=0.7,
        rules=RULES,
        trip_minutes=60,
    )
    (plan,) = plans
    assert plan.units == 30.0  # what the receiver would miss, not more
    hours, minutes = plan.leave_by.split(":")
    assert int(hours) * 60 + int(minutes) + 60 <= RULES.must_arrive_before_hour * 60  # before 11 am
    assert plan.van_cost_inr == RULES.van_cost_inr
    assert plan.net_benefit_inr > 0
