"""Calendar days for store managers and farmers, graphs for area managers, a 3-day farmer window."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from harabhara.contracts import FarmerVolumeForecast, OutcomeRecord, Range
from tests.backend.conftest import NOW, TODAY, Env, make_suggestion

V1 = "/api/v1"
WHEN = datetime(2026, 11, 1, 22, 0, tzinfo=NOW.tzinfo)


def closing(
    day: date, store: str, sku: str, sold: float, wasted: float, out: bool
) -> OutcomeRecord:
    return OutcomeRecord(
        kind="closing", on=day, store_id=store, sku_id=sku, units_sold=sold,
        units_wasted=wasted, sold_out=out, recorded_by="t", recorded_at=WHEN,
    )  # fmt: skip


def bought(
    day: date, sku: str, units: float, source: Literal["farmer_group", "spot"]
) -> OutcomeRecord:
    return OutcomeRecord(
        kind="purchase", on=day, sku_id=sku, units_bought=units, source=source,
        recorded_by="t", recorded_at=WHEN,
    )  # fmt: skip


def est(day: date, sku: str = "tomato") -> FarmerVolumeForecast:
    return FarmerVolumeForecast(
        fpo_id="fpo-1", sku_id=sku, on=day, volume=Range(low=1, likely=2, high=3)
    )


# ---- farmers: three days only, and a calendar for the past ---------------------------------


def test_a_farmer_group_sees_three_days_of_estimate_and_no_more(env: Env) -> None:
    env.storage.put_farmer_forecasts([est(TODAY + timedelta(days=d)) for d in range(-3, 7)])
    r = env.client.get(f"{V1}/farmers/forecast", headers=env.login("5555"))
    assert r.status_code == 200
    days = sorted(row["on"] for row in r.json())
    assert days == [(TODAY + timedelta(days=d)).isoformat() for d in range(3)]


def test_the_farmer_calendar_shows_the_estimate_then_and_what_was_bought(env: Env) -> None:
    day = TODAY - timedelta(days=2)
    env.storage.put_farmer_forecasts([est(day)])
    env.storage.put_outcome(bought(day, "tomato", 120, "farmer_group"))
    env.storage.put_outcome(bought(day, "tomato", 999, "spot"))  # spot buying is not theirs
    r = env.client.get(f"{V1}/farmers/day?date={day}", headers=env.login("5555"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["label"] == "estimate"
    assert body["rows"] == [
        {
            "sku_id": "tomato",
            "fpo_id": "fpo-1",
            "estimate": {"low": 1.0, "likely": 2.0, "high": 3.0},
            "bought_from_groups": 120.0,
        }
    ]
    assert body["last_day"] == TODAY.isoformat()
    assert body["first_day"] < day.isoformat()  # the calendar goes back further than one day


def test_the_farmer_calendar_refuses_the_future_and_too_far_back(env: Env) -> None:
    h = env.login("5555")
    assert (
        env.client.get(f"{V1}/farmers/day?date={TODAY + timedelta(days=1)}", headers=h).status_code
        == 422
    )
    assert (
        env.client.get(
            f"{V1}/farmers/day?date={TODAY - timedelta(days=400)}", headers=h
        ).status_code
        == 422
    )
    assert (
        env.client.get(f"{V1}/farmers/day?date={TODAY}", headers=env.login("1111")).status_code
        == 403
    )


# ---- store manager: pick a day -------------------------------------------------------------


def test_a_store_manager_picks_a_past_day_and_sees_only_their_own_store(env: Env) -> None:
    day = TODAY - timedelta(days=4)
    mine = make_suggestion("o1", "S1").model_copy(update={"created_at": NOW - timedelta(days=4)})
    other = make_suggestion("o2", "S2").model_copy(update={"created_at": NOW - timedelta(days=4)})
    env.storage.create_suggestion(mine)
    env.storage.create_suggestion(other)
    env.storage.put_outcome(closing(day, "S1", "tomato", 80, 20, True))
    env.storage.put_outcome(closing(day, "S2", "tomato", 5, 5, False))
    r = env.client.get(f"{V1}/history/day?date={day}", headers=env.login("1111"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["day"]["orders_made"] == 1
    assert [o["sku_id"] for o in body["day"]["orders"]] == ["tomato"]
    assert (body["day"]["waste_pct"], body["day"]["stockout_pct"]) == (20.0, 100.0)
    assert body["first_day"] < day.isoformat()
    assert body["last_day"] == TODAY.isoformat()


def test_a_day_with_nothing_on_record_says_so_and_the_calendar_has_limits(env: Env) -> None:
    h = env.login("1111")
    quiet = env.client.get(f"{V1}/history/day?date={TODAY - timedelta(days=3)}", headers=h).json()
    assert quiet["day"]["orders_made"] == 0
    assert quiet["day"]["waste_pct"] is None  # unknown, not zero
    assert (
        env.client.get(f"{V1}/history/day?date={TODAY + timedelta(days=1)}", headers=h).status_code
        == 422
    )
    assert (
        env.client.get(
            f"{V1}/history/day?date={TODAY - timedelta(days=400)}", headers=h
        ).status_code
        == 422
    )
    assert (
        env.client.get(f"{V1}/history/day?date={TODAY}", headers=env.login("3333")).status_code
        == 403
    )


# ---- area managers: weekly and monthly graphs ----------------------------------------------


def test_the_weekly_and_monthly_series_have_the_configured_length_and_keep_gaps(env: Env) -> None:
    h = env.login("3333")
    env.storage.put_outcome(closing(TODAY - timedelta(days=1), "S1", "tomato", 80, 20, True))
    env.storage.put_outcome(bought(TODAY - timedelta(days=1), "tomato", 30, "farmer_group"))
    env.storage.put_outcome(bought(TODAY - timedelta(days=1), "tomato", 70, "spot"))
    week = env.client.get(f"{V1}/history/series?period=week", headers=h).json()
    month = env.client.get(f"{V1}/history/series?period=month", headers=h).json()
    assert (len(week["points"]), len(month["points"])) == (7, 30)
    assert week["scope"] == "chain"
    point = week["points"][-2]
    assert (point["waste_pct"], point["stockout_pct"]) == (20.0, 100.0)  # together, always
    assert week["points"][0]["waste_pct"] is None  # a day nobody closed is a gap, not zero
    assert week["days_with_closing"] == 1
    assert week["farmer_share"] == 0.3


def test_a_series_can_be_asked_for_one_store_by_an_area_manager(env: Env) -> None:
    env.storage.put_outcome(closing(TODAY - timedelta(days=1), "S1", "tomato", 80, 20, True))
    r = env.client.get(f"{V1}/history/series?period=week&store_id=S1", headers=env.login("3333"))
    assert r.status_code == 200, r.text
    assert r.json()["scope"] == "S1"
    assert env.client.get(f"{V1}/history/series", headers=env.login("4444")).status_code == 403


# ---- store manager: my numbers -------------------------------------------------------------


def _two_stores(env: Env) -> None:
    day = TODAY - timedelta(days=1)
    env.storage.put_outcome(closing(day, "S1", "tomato", 80, 20, True))  # 20% waste, ran out
    env.storage.put_outcome(closing(day, "S1", "onion", 100, 0, False))
    env.storage.put_outcome(closing(day, "S2", "tomato", 100, 0, False))  # another store, no waste


def test_my_numbers_are_my_store_only_with_the_all_stores_figure_beside_them(env: Env) -> None:
    _two_stores(env)
    body = env.client.get(f"{V1}/history/series?period=week", headers=env.login("1111")).json()
    assert body["scope"] == "S1"
    assert body["store_ids"] == ["S1"]
    assert body["waste_pct"] == round(100 * 20 / 200, 1)  # my 20 thrown away of 200 handled
    assert body["stockout_pct"] == 50.0  # tomato ran out, onion did not
    assert body["chain_waste_pct"] == round(100 * 20 / 300, 1)  # all stores, for comparison
    assert body["chain_stockout_pct"] == round(100 * 1 / 3, 1)
    assert body["talk"] == []  # what to raise with a manager is for their area manager


def test_my_numbers_name_what_was_thrown_away_and_what_ran_out(env: Env) -> None:
    _two_stores(env)
    body = env.client.get(f"{V1}/history/series?period=month", headers=env.login("1111")).json()
    assert body["period_top_waste"] == [{"sku_id": "tomato", "units": 20.0}]
    assert body["period_ran_out"] == [{"sku_id": "tomato", "stores": 1}]


def test_a_store_manager_cannot_ask_for_another_store(env: Env) -> None:
    _two_stores(env)
    h = env.login("1111")
    assert env.client.get(f"{V1}/history/series?store_id=S2", headers=h).status_code == 403
    assert env.client.get(f"{V1}/history/series?store_id=S1", headers=h).status_code == 200
