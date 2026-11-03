from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from harabhara.models.shelf_life import (
    FEATURES,
    TARGET,
    ShelfLifeModel,
    rule_cap,
    rule_days,
)
from harabhara.settings import load_config
from harabhara.settings.schema import ShelfLifeParams

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "work" / "PS-10_procurement_and_inventory.xlsx"

RULES = pd.DataFrame(
    {
        "sku_id": ["P01", "P13"],
        "shelf_life_days_grade_A_ambient": [5, 2],
        "shelf_life_days_grade_B_ambient": [4, 1],
        "shelf_life_days_grade_C_ambient": [3, 1],
    }
)
SMALL = ShelfLifeParams(
    quantiles=(0.1, 0.5, 0.9),
    iterations=40,
    depth=3,
    learning_rate=0.2,
    seed=0,
    fit_until="2026-05-31",
    training_period_end="2026-08-05",
)


def _qc(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sku = rng.choice(["P01", "P13"], n)
    age = rng.integers(0, 4, n)
    temp = rng.normal(26, 4, n)
    life = np.where(sku == "P01", 5, 2) - 0.5 * age - 0.15 * np.clip(temp - 26, 0, None)
    return pd.DataFrame(
        {
            "sku_id": sku,
            "source_type": rng.choice(["FPO contract", "Mandi auction"], n),
            "grade_assigned": rng.choice(["A", "B", "C"], n),
            "days_since_harvest": age,
            "receipt_temperature_c": temp,
            "firmness_score_1_10": rng.uniform(4, 10, n),
            "colour_score_1_10": rng.uniform(4, 10, n),
            "visible_defects_pct": rng.uniform(0, 12, n),
            TARGET: np.clip(np.round(life + rng.normal(0, 0.4, n)), 0, None).astype(int),
        }
    )


def test_rule_follows_the_assigned_grade() -> None:
    qc = pd.DataFrame({"sku_id": ["P01", "P01", "P13"], "grade_assigned": ["A", "C", "B"]})
    assert list(rule_days(qc, RULES)) == [5, 3, 1]


def test_warm_arrivals_lose_the_playbook_penalty() -> None:
    receiving = load_config().rules.receiving
    qc = pd.DataFrame(
        {
            "sku_id": ["P01", "P01"],
            "grade_assigned": ["A", "A"],
            "receipt_temperature_c": [
                receiving.hot_arrival_temp_c - 1,
                receiving.hot_arrival_temp_c + 1,
            ],
        }
    )
    cap = rule_cap(qc, RULES, receiving)
    assert cap.iloc[0] - cap.iloc[1] == receiving.hot_arrival_life_penalty_days


def test_estimate_is_ordered_and_never_exceeds_the_rule() -> None:
    receiving = load_config().rules.receiving
    qc = _qc()
    model = ShelfLifeModel(SMALL).fit(qc)
    estimate = model.predict(qc, rule_cap(qc, RULES, receiving))
    assert (estimate.low <= estimate.likely + 1e-9).all()
    assert (estimate.likely <= estimate.high + 1e-9).all()
    assert (estimate.high <= estimate.rule + 1e-9).all()  # guardrail G06
    assert (estimate.low >= 0).all()


def test_a_cap_below_the_prediction_is_flagged_and_enforced() -> None:
    qc = _qc()
    model = ShelfLifeModel(SMALL).fit(qc)
    tight = pd.Series(0.5, index=qc.index)
    estimate = model.predict(qc, tight)
    assert (estimate.high <= 0.5).all()
    assert estimate.capped.any()


def test_whole_days_round_down() -> None:
    qc = _qc(60)
    model = ShelfLifeModel(SMALL).fit(qc)
    estimate = model.predict(qc, pd.Series(10.0, index=qc.index))
    assert (estimate.likely_days() <= estimate.likely).all()


def test_predicting_before_fitting_is_an_error() -> None:
    qc = _qc(10)
    with pytest.raises(RuntimeError, match="not fitted"):
        ShelfLifeModel(SMALL).predict(qc, pd.Series(3.0, index=qc.index))


def test_features_are_only_what_qc_measures() -> None:
    assert not any("humid" in f or "rain" in f or "max_temp" in f for f in FEATURES)


@pytest.mark.skipif(not PACK.exists(), reason="data pack is not in the repository")
def test_real_qc_beats_the_fixed_rule_on_unseen_dates() -> None:
    cfg = load_config()
    p = cfg.modeling.shelf_life
    qc = pd.read_excel(PACK, sheet_name="qc_samples")
    rules = pd.read_excel(PACK, sheet_name="shelf_life_rules")
    qc["date"] = pd.to_datetime(qc["date"])
    fit = qc[qc["date"] <= pd.Timestamp(p.fit_until)]
    valid = qc[
        (qc["date"] > pd.Timestamp(p.fit_until))
        & (qc["date"] <= pd.Timestamp(p.training_period_end))
    ]
    model = ShelfLifeModel(p).fit(fit)
    cap = rule_cap(valid, rules, cfg.rules.receiving)
    estimate = model.predict(valid, cap)
    model_mae = (estimate.likely - valid[TARGET]).abs().mean()
    rule_mae = (cap - valid[TARGET]).abs().mean()
    assert model_mae < rule_mae
