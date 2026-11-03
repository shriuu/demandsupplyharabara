"""The demand forecast: one global CatBoost model with a low, likely and high output.

The model is shared across all stores and products, so new products borrow from similar ones.
The three outputs are the 10th, 50th and 90th percentiles (``config/modeling.yaml``), which are
then calibrated so the stated range holds the stated share of outcomes
(``harabhara.models.calibrate``). Horizon (1 to 3 days ahead) is a feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from harabhara.features.build import CATEGORICAL
from harabhara.settings.schema import DemandParams


class DemandModel:
    def __init__(self, params: DemandParams) -> None:
        self._params = params
        self._models: list[CatBoostRegressor] = []
        self._columns: list[str] = []
        self._known_skus: frozenset[str] = frozenset()

    @property
    def columns(self) -> list[str]:
        return list(self._columns)

    def unseen(self, examples: pd.DataFrame) -> pd.Series:
        """True for products the model never trained on (new product, or no history in its fit)."""
        return ~examples["sku_id"].astype(str).isin(self._known_skus)

    def fit(
        self, examples: pd.DataFrame, columns: list[str], target: str = "y_demand"
    ) -> DemandModel:
        p = self._params
        self._columns = list(columns)
        self._known_skus = frozenset(examples["sku_id"].astype(str).unique())
        cats = [c for c in CATEGORICAL if c in columns]
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
                cat_features=cats,
            )
            model.fit(examples[columns], examples[target])
            self._models.append(model)
        return self

    def predict(self, examples: pd.DataFrame) -> pd.DataFrame:
        if not self._models:
            msg = "model is not fitted"
            raise RuntimeError(msg)
        raw = np.column_stack([m.predict(examples[self._columns]) for m in self._models])
        raw.sort(axis=1)  # quantile models can cross; keep low <= likely <= high
        raw = np.clip(raw, 0, None)
        return pd.DataFrame(
            {"low": raw[:, 0], "likely": raw[:, 1], "high": raw[:, 2]}, index=examples.index
        )

    def importance(self) -> pd.Series:
        """Mean importance of each feature across the three outputs, largest first."""
        scores = pd.concat(
            [pd.Series(m.get_feature_importance(), index=self._columns) for m in self._models],
            axis=1,
        )
        return scores.mean(axis=1).sort_values(ascending=False)
