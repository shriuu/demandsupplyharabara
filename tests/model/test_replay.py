from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from harabhara.sim.replay import ReplayParams, replay
from harabhara.sim.simulator import simulate_history

START, END = date(2026, 2, 1), date(2026, 2, 20)
Q = (0.1, 0.5, 0.9)


def _panel() -> pd.DataFrame:
    rows = []
    for day in pd.date_range("2026-01-01", "2026-02-20"):
        for store, demand, received in (("S01", 90.0, 60.0), ("S02", 30.0, 60.0)):
            rows.append(
                {
                    "date": day,
                    "store_id": store,
                    "sku_id": "P13",
                    "in_season": True,
                    "demand": demand,
                    "received_units": received,
                    "selling_price": 13.0,
                }
            )
    return pd.DataFrame(rows)


def _forecasts() -> pd.DataFrame:
    rows = []
    for day in pd.date_range(START, END):
        for store, likely in (("S01", 90.0), ("S02", 30.0)):
            rows.append(
                {
                    "store_id": store,
                    "sku_id": "P13",
                    "target_date": day,
                    "low": likely * 0.8,
                    "likely": likely,
                    "high": likely * 1.2,
                }
            )
    return pd.DataFrame(rows).set_index(["store_id", "sku_id", "target_date"])[
        ["low", "likely", "high"]
    ]


def _share() -> pd.Series:
    index = pd.MultiIndex.from_product(
        [pd.date_range("2026-01-01", END), ["P13"]], names=["date", "sku_id"]
    )
    return pd.Series(0.4, index=index)


def _params(floor: float = 0.0) -> ReplayParams:
    return ReplayParams(
        life_days={"P13": 2},
        unit_cost={"P13": 7.0},
        markdown_pct=30.0,
        sales_order="freshest_first",
        quantiles=Q,
        allocation_steps=200,
        waste_exponent=1.0,
        basket_allowance=None,
        service_floor=floor,
    )


def test_the_managers_scenario_matches_the_plain_simulator() -> None:
    panel = _panel()
    ours = replay(panel, _forecasts(), _share(), _params(), START, END, "managers")
    plain = simulate_history(panel, {"P13": 2}, "freshest_first")
    plain = plain[(plain["date"] >= pd.Timestamp(START)) & (plain["date"] <= pd.Timestamp(END))]
    assert ours["binned"].sum() == pytest.approx(plain["sim_binned"].sum())
    assert ours["lost"].sum() == pytest.approx(plain["sim_lost"].sum())


def test_reallocating_never_changes_the_total_supply() -> None:
    panel = _panel()
    base = replay(panel, _forecasts(), _share(), _params(), START, END, "managers")
    ours = replay(panel, _forecasts(), _share(), _params(), START, END, "reallocate")
    assert ours["delivered"].sum() == pytest.approx(base["delivered"].sum())


def test_moving_supply_to_the_busy_store_cuts_waste_and_lost_sales() -> None:
    panel = _panel()
    base = replay(panel, _forecasts(), _share(), _params(), START, END, "managers")
    ours = replay(panel, _forecasts(), _share(), _params(), START, END, "reallocate")
    assert ours["binned"].sum() < base["binned"].sum()
    assert ours["lost"].sum() < base["lost"].sum()


def test_trimming_never_delivers_less_than_the_committed_farmer_volume() -> None:
    panel = _panel()
    ours = replay(panel, _forecasts(), _share(), _params(floor=0.0), START, END, "reallocate_trim")
    per_day = ours.groupby("date").agg(
        delivered=("delivered", "sum"), committed=("committed_sku_day", "first")
    )
    assert (per_day["delivered"] + 1e-6 >= per_day["committed"]).all()


def test_a_missing_forecast_falls_back_to_the_managers_split() -> None:
    panel = _panel()
    base = replay(panel, _forecasts(), _share(), _params(), START, END, "managers")
    ours = replay(panel, _forecasts().iloc[0:0], _share(), _params(), START, END, "reallocate")
    assert ours["delivered"].tolist() == base["delivered"].tolist()
