"""Remaining shelf life per lot from the quality check at receipt (CLAUDE.md s10).

Three boosted-tree models give a low, likely and high estimate of sellable days from what QC
measures on arrival: age, temperature, firmness, colour, defects, grade, source and product.
Ambient weather is deliberately not a feature (it added nothing; see docs/shelf_life.md).

The playbook rule always wins (guardrail G06): every estimate is capped at the rule's last
sellable day, reduced by a day for warm arrivals as the playbook says. The rule and the model
are both returned so a screen can show both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from harabhara.settings.schema import Receiving, ShelfLifeParams

CATEGORICAL = ["sku_id", "source_type", "grade_assigned"]
NUMERIC = [
    "days_since_harvest",
    "receipt_temperature_c",
    "firmness_score_1_10",
    "colour_score_1_10",
    "visible_defects_pct",
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "observed_sellable_days"


def rule_days(qc: pd.DataFrame, rules: pd.DataFrame) -> pd.Series:
    """The playbook's last sellable day for each lot, by assigned grade, before any penalty."""
    merged = qc[["sku_id", "grade_assigned"]].merge(rules, on="sku_id", how="left")
    chosen = np.select(
        [merged["grade_assigned"] == "A", merged["grade_assigned"] == "B"],
        [merged["shelf_life_days_grade_A_ambient"], merged["shelf_life_days_grade_B_ambient"]],
        merged["shelf_life_days_grade_C_ambient"],
    )
    return pd.Series(chosen, index=qc.index, dtype=float)


def rule_cap(qc: pd.DataFrame, rules: pd.DataFrame, receiving: Receiving) -> pd.Series:
    """Rule days, less the playbook's penalty for produce arriving warmer than the limit."""
    base = rule_days(qc, rules)
    warm = qc["receipt_temperature_c"] > receiving.hot_arrival_temp_c
    return (base - warm * receiving.hot_arrival_life_penalty_days).clip(lower=0)


@dataclass(frozen=True)
class Estimate:
    """Remaining sellable days per lot, as a range, next to the rule it is capped by."""

    low: pd.Series
    likely: pd.Series
    high: pd.Series
    rule: pd.Series
    capped: pd.Series  # True where the model said more than the rule allows

    def likely_days(self) -> pd.Series:
        """Whole sellable days to plan with: rounded down, so the ledger never over-promises."""
        return self.likely.apply(math.floor).astype(int)


class ShelfLifeModel:
    def __init__(self, params: ShelfLifeParams) -> None:
        self._params = params
        self._models: list[CatBoostRegressor] = []

    def fit(self, qc: pd.DataFrame) -> ShelfLifeModel:
        p = self._params
        self._models = []
        for alpha in p.quantiles:
            model = CatBoostRegressor(
                loss_function=f"Quantile:alpha={alpha}",
                iterations=p.iterations,
                depth=p.depth,
                learning_rate=p.learning_rate,
                random_seed=p.seed,
                verbose=False,
                allow_writing_files=False,
                thread_count=1,
                cat_features=CATEGORICAL,
            )
            model.fit(qc[FEATURES], qc[TARGET])
            self._models.append(model)
        return self

    def predict(self, qc: pd.DataFrame, cap: pd.Series) -> Estimate:
        if not self._models:
            msg = "model is not fitted"
            raise RuntimeError(msg)
        raw = np.column_stack([m.predict(qc[FEATURES]) for m in self._models])
        raw.sort(axis=1)  # quantile models can cross; keep low <= likely <= high
        raw = np.clip(raw, 0, None)
        limit = cap.to_numpy(dtype=float)[:, None]
        bounded = np.minimum(raw, limit)
        index = qc.index
        return Estimate(
            low=pd.Series(bounded[:, 0], index=index),
            likely=pd.Series(bounded[:, 1], index=index),
            high=pd.Series(bounded[:, 2], index=index),
            rule=pd.Series(limit[:, 0], index=index),
            capped=pd.Series(raw[:, 1] > limit[:, 0], index=index),
        )
