"""Load the data pack and build the modelling panel and examples in one repeatable step."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from harabhara.data.clean import CleanReport, clean_sales, load_sales, load_sheet
from harabhara.features.build import assemble_panel, make_examples
from harabhara.features.hidden_demand import estimate_demand, hours_by_format
from harabhara.settings.schema import AppConfig


def build_panel(
    sales_path: Path, external_path: Path, cfg: AppConfig
) -> tuple[pd.DataFrame, CleanReport]:
    cleaned = clean_sales(load_sales(sales_path))
    stores = load_sheet(sales_path, "stores")
    skus = load_sheet(sales_path, "skus")
    calendar = load_sheet(external_path, "calendar")
    weather = load_sheet(external_path, "weather_daily")
    mandi = load_sheet(external_path, "mandi_prices")

    with_format = cleaned.data.merge(stores[["store_id", "format"]], on="store_id")
    demand = estimate_demand(
        with_format, hours_by_format(cfg.schedule.store_hours), cfg.modeling.hidden_demand
    )
    return assemble_panel(demand, stores, skus, calendar, weather, mandi), cleaned.report


def build_examples(panel: pd.DataFrame, cfg: AppConfig) -> pd.DataFrame:
    horizons = cfg.rules.ordering.forecast_horizon_days
    return make_examples(panel, cfg.modeling.demand, horizons)
