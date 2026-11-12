"""The pipeline: demo-day mapping, the holdout guard, and (with the data pack) the full run."""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from harabhara.contracts import (
    FarmerVolumeForecast,
    Forecast,
    Projection,
    ProjectionDay,
    Range,
    Scorecard,
)
from harabhara.data.prepare import build_examples
from harabhara.pipeline.forecast import fit_forecaster
from harabhara.pipeline.inputs import PackData, last_training_day, load_pack
from harabhara.pipeline.run import Outputs, build_outputs, check_not_holdout, shift_to_today
from harabhara.settings import AppConfig, load_config
from tests.rules.conftest import markdown, suggestion, surplus

WORK = Path(__file__).resolve().parents[2] / "work"
HAVE_PACK = (WORK / "PS-10_store_sales_daily.xlsx").exists()
AS_OF = date(2026, 8, 1)  # a Saturday inside the training period
RANGE = Range(low=8, likely=10, high=14)


# ---- no data pack needed -------------------------------------------------------------------
def test_a_run_may_not_start_inside_the_holdout() -> None:
    last = date(2026, 8, 5)
    check_not_holdout(last, last)
    check_not_holdout(date(2026, 7, 1), last)
    with pytest.raises(ValueError, match="holdout"):
        check_not_holdout(date(2026, 8, 6), last)


def _outputs() -> Outputs:
    day = AS_OF
    return Outputs(
        forecasts=[
            Forecast(
                store_id="S01", sku_id="P01", target_date=day + timedelta(days=1), horizon_days=1,
                demand=RANGE, model_version="m", data_snapshot_id="d", config_digest="c",
            )
        ],
        suggestions=[suggestion(markdown(), deadline=datetime(2026, 8, 1, 9, 0, tzinfo=UTC))],
        farmer=[
            FarmerVolumeForecast(
                fpo_id="FPO-01", sku_id="P01", on=day + timedelta(days=1), volume=RANGE
            )
        ],
        scorecards=[
            Scorecard(
                scope="chain", period_start=day - timedelta(days=27), period_end=day,
                waste_pct=7.0, stockout_pct=9.0, farmer_share=0.3, farmer_share_definition="x",
            )
        ],
        trimming=[
            {
                "on": day + timedelta(days=1),
                "sku_id": "P01",
                "spot_units_to_trim": 12,
                "reason": "r",
            }
        ],
        projections=[
            Projection(
                store_id="S01", sku_id="P01", as_of=day - timedelta(days=1),
                days=[
                    ProjectionDay(
                        day=1, on=day, demand=RANGE, sold=RANGE, lost_sales=RANGE,
                        expected_waste=RANGE, closing_stock=RANGE,
                    )
                ],
                model_version="m", data_snapshot_id="d", config_digest="c",
            )
        ],
    )  # fmt: skip


def test_the_demo_day_mapping_moves_every_date_and_keeps_the_content() -> None:
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    delta = now.date() - AS_OF
    out = shift_to_today(_outputs(), delta, "demo20261104", now, keep_open_hours=6)
    assert out.forecasts[0].target_date == AS_OF + timedelta(days=1) + delta
    assert out.forecasts[0].demand == RANGE
    assert out.farmer[0].on == AS_OF + timedelta(days=1) + delta
    assert out.scorecards[0].period_end == AS_OF + delta
    assert out.trimming[0]["on"] == AS_OF + timedelta(days=1) + delta
    assert out.projections[0].days[0].on == AS_OF + delta
    assert out.suggestions[0].payload == _outputs().suggestions[0].payload
    assert out.suggestions[0].reason == _outputs().suggestions[0].reason


def test_the_demo_day_mapping_moves_a_surplus_pickup_day_with_everything_else() -> None:
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    delta = now.date() - AS_OF
    out = Outputs(suggestions=[suggestion(surplus(pickup_date=AS_OF + timedelta(days=1)))])
    shifted = shift_to_today(out, delta, "t", now, keep_open_hours=6)
    payload = shifted.suggestions[0].payload
    assert payload.kind == "surplus"
    assert payload.pickup_date == AS_OF + timedelta(days=1) + delta  # still "tomorrow", not July


def test_no_suggestion_is_already_expired_after_the_mapping() -> None:
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    out = shift_to_today(_outputs(), now.date() - AS_OF, "t", now, keep_open_hours=6)
    assert all(s.deadline >= now + timedelta(hours=6) for s in out.suggestions)


def test_ids_carry_the_tag_so_a_later_load_does_not_collide() -> None:
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    a = shift_to_today(_outputs(), now.date() - AS_OF, "demo20261104", now, 6)
    b = shift_to_today(_outputs(), now.date() - AS_OF, "demo20261105", now, 6)
    assert a.suggestions[0].id != b.suggestions[0].id
    assert a.suggestions[0].id.endswith("@demo20261104")


# ---- needs the data pack (slow) ------------------------------------------------------------
def _fast_cfg() -> AppConfig:
    cfg = load_config()
    demand = cfg.modeling.demand.model_copy(update={"iterations": 40, "depth": 4})
    return cfg.model_copy(update={"modeling": cfg.modeling.model_copy(update={"demand": demand})})


@pytest.fixture(scope="module")
def pack() -> PackData:
    return load_pack(WORK, _fast_cfg())


@pytest.fixture(scope="module")
def base_outputs(pack: PackData) -> Outputs:
    return build_outputs(pack, fit_forecaster(pack, AS_OF - timedelta(days=1)), AS_OF)


def _snapshot(out: Outputs) -> dict[str, object]:
    return {
        "forecasts": [f.model_dump(mode="json") for f in out.forecasts],
        "suggestions": [s.model_dump(mode="json") for s in out.suggestions],
        "farmer": [f.model_dump(mode="json") for f in out.farmer],
        "scorecards": [c.model_dump(mode="json") for c in out.scorecards],
        "trimming": [{**t, "on": str(t["on"])} for t in out.trimming],
        "projections": [p.model_dump(mode="json") for p in out.projections],
    }


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository")
def test_the_last_training_day_is_known_and_the_holdout_follows(pack: PackData) -> None:
    assert last_training_day(pack.panel) == date(2026, 8, 5)


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository")
def test_a_full_run_produces_valid_checked_output(base_outputs: Outputs) -> None:
    out = base_outputs
    assert out.suggestions
    ids = [s.id for s in out.suggestions]
    assert len(ids) == len(set(ids))
    assert {s.state for s in out.suggestions} == {"proposed"}
    assert all(s.reason.endswith(".") and "\n" not in s.reason for s in out.suggestions)
    kinds = {s.payload.kind for s in out.suggestions}
    assert {"order", "markdown"} <= kinds
    targets = {f.target_date for f in out.forecasts}
    assert targets == {AS_OF + timedelta(days=n) for n in (1, 2, 3)}
    assert {f.horizon_days for f in out.forecasts} == {1, 2, 3}


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository")
def test_scorecards_always_carry_waste_stockouts_and_farmer_share(base_outputs: Outputs) -> None:
    chain = next(c for c in base_outputs.scorecards if c.scope == "chain")
    assert 0 < chain.waste_pct < 100
    assert 0 < chain.stockout_pct < 100
    assert chain.farmer_share is not None
    assert all(
        c.farmer_share is not None or c.farmer_share_definition for c in base_outputs.scorecards
    )
    assert len(base_outputs.scorecards) == 13  # the chain and twelve stores


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository")
def test_farmer_volumes_are_labelled_estimates_for_the_next_three_days(
    base_outputs: Outputs,
) -> None:
    assert base_outputs.farmer
    assert {f.label for f in base_outputs.farmer} == {"estimate"}
    assert {f.on for f in base_outputs.farmer} <= {AS_OF + timedelta(days=n) for n in (1, 2, 3)}


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository")
def test_trimming_only_ever_reduces_spot_buying(base_outputs: Outputs, pack: PackData) -> None:
    ordered = (
        pack.panel[(pack.panel["date"] == pd.Timestamp(AS_OF)) & pack.panel["in_season"]]
        .groupby("sku_id")["order_placed_for_tomorrow"]
        .sum()
    )
    for advice in base_outputs.trimming:
        assert advice["spot_units_to_trim"] > 0
        assert advice["spot_units_to_trim"] <= ordered[advice["sku_id"]]
        assert "spot market" in advice["reason"]


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_PACK, reason="data pack is not in the repository")
def test_outputs_ignore_everything_dated_after_the_as_of_day(
    pack: PackData, base_outputs: Outputs
) -> None:
    """Scramble every outcome after the as-of day: the output must not change at all."""
    cfg = _fast_cfg()
    panel = pack.panel.copy()
    future = panel["date"] > pd.Timestamp(AS_OF)
    rng = np.random.default_rng(7)
    for column in (
        "demand", "sold", "sold_corrected", "received_units", "order_placed_for_tomorrow",
        "wastage_units", "closing_stock", "opening_stock", "units_sold_full_price",
        "units_sold_markdown", "selling_price", "modal_price_inr", "arrivals_tonnes",
    ):  # fmt: skip
        panel[column] = panel[column].astype(float)
        panel.loc[future, column] = rng.uniform(1, 500, int(future.sum()))
    panel.loc[future, "stockout_flag"] = ~panel.loc[future, "stockout_flag"].astype(bool)
    panel.loc[future, "promo_flag"] = ~panel.loc[future, "promo_flag"].astype(bool)

    scrambled = dataclasses.replace(pack, panel=panel, examples=build_examples(panel, cfg))
    again = build_outputs(scrambled, fit_forecaster(scrambled, AS_OF - timedelta(days=1)), AS_OF)
    assert _snapshot(again) == _snapshot(base_outputs)
