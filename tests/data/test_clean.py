from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from harabhara.data.clean import clean_sales, load_sales

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "work" / "PS-10_store_sales_daily.xlsx"


def _row(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "date": pd.Timestamp("2026-01-05"),
        "store_id": "S01",
        "sku_id": "P01",
        "in_season": True,
        "opening_stock": 10,
        "received_units": 90,
        "units_sold_full_price": 70,
        "units_sold_markdown": 10,
        "wastage_units": 5.0,
        "closing_stock": 15,
        "stockout_flag": False,
    }
    return base | over


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def test_exact_duplicates_are_removed_and_counted() -> None:
    result = clean_sales(_frame(_row(), _row(), _row(sku_id="P02")))
    assert result.report.duplicates_removed == 1
    assert len(result.data) == 2


def test_conflicting_rows_with_the_same_key_are_an_error() -> None:
    with pytest.raises(ValueError, match="conflicting"):
        clean_sales(_frame(_row(), _row(closing_stock=20, wastage_units=0.0)))


def test_blank_waste_is_rebuilt_from_stock_arithmetic() -> None:
    result = clean_sales(_frame(_row(wastage_units=float("nan"))))
    row = result.data.iloc[0]
    assert row["wastage_units"] == 5.0  # 10 + 90 - 80 - 15
    assert bool(row["waste_rebuilt"]) is True
    assert result.report.blank_waste_rebuilt == 1


def test_till_outage_is_detected_and_sales_rebuilt() -> None:
    outage = _row(units_sold_full_price=0, units_sold_markdown=0, wastage_units=5.0)
    outage |= {"closing_stock": 15}
    result = clean_sales(_frame(outage))
    row = result.data.iloc[0]
    assert bool(row["outage"]) is True
    assert row["sold_corrected"] == 80  # 10 + 90 - 5 - 15
    assert bool(row["usable_for_targets"]) is False
    assert result.report.outage_store_days == 1


def test_a_genuinely_slow_day_is_not_an_outage() -> None:
    quiet = _row(
        units_sold_full_price=0,
        units_sold_markdown=0,
        wastage_units=0.0,
        closing_stock=100,
    )
    result = clean_sales(_frame(quiet))
    assert bool(result.data.iloc[0]["outage"]) is False


def test_out_of_season_rows_are_not_targets() -> None:
    off = _row(
        in_season=False,
        opening_stock=0,
        received_units=0,
        units_sold_full_price=0,
        units_sold_markdown=0,
        wastage_units=0.0,
        closing_stock=0,
    )
    result = clean_sales(_frame(off))
    assert bool(result.data.iloc[0]["usable_for_targets"]) is False
    assert result.report.out_of_season_rows == 1


def test_input_is_not_modified() -> None:
    raw = _frame(_row(wastage_units=float("nan")), _row(sku_id="P02"))
    before = raw.copy()
    clean_sales(raw)
    pd.testing.assert_frame_equal(raw, before)


def test_unbalanced_stock_that_is_not_an_outage_is_an_error() -> None:
    with pytest.raises(ValueError, match="stock arithmetic"):
        clean_sales(_frame(_row(closing_stock=40)))


@pytest.mark.skipif(not REAL.exists(), reason="data pack is not in the repository")
def test_real_data_pack_matches_the_documented_issues() -> None:
    result = clean_sales(load_sales(REAL))
    report = result.report
    assert report.duplicates_removed == 25
    assert report.blank_waste_rebuilt == 120
    assert report.outage_store_days == 3  # S07, 10 to 12 Feb 2026
    stores = result.data.loc[result.data["outage"], "store_id"].unique()
    assert list(stores) == ["S07"]
