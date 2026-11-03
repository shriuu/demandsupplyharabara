"""Intake and cleaning of ``sales_daily`` (CLAUDE.md s7 factor 11, s10 step 1).

The input is never modified. Every repair is counted in a ``CleanReport`` so a run can be
audited, and repairs are flagged on the rows themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

KEY = ["date", "store_id", "sku_id"]


@dataclass(frozen=True)
class CleanReport:
    rows_in: int
    duplicates_removed: int
    blank_waste_rebuilt: int
    outage_rows: int
    outage_store_days: int
    out_of_season_rows: int
    rows_out: int


@dataclass(frozen=True)
class CleanResult:
    data: pd.DataFrame
    report: CleanReport


def load_sales(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="sales_daily")


def load_sheet(path: Path, sheet: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet)


def _balance(df: pd.DataFrame, waste: pd.Series) -> pd.Series:
    """Units unaccounted for: opening + received - sold - waste - closing."""
    sold = df["units_sold_full_price"] + df["units_sold_markdown"]
    return df["opening_stock"] + df["received_units"] - sold - waste - df["closing_stock"]


def clean_sales(raw: pd.DataFrame) -> CleanResult:
    """Return cleaned rows plus a report.

    Added columns:
    - ``sold``: full-price plus markdown units as recorded.
    - ``waste_rebuilt``: True where a blank wastage was rebuilt from stock arithmetic.
    - ``outage``: True where the till recorded zero sales although stock moved (POS outage).
    - ``sold_corrected``: ``sold``, or the units implied by stock arithmetic on outage rows.
    - ``usable_for_targets``: in season and not an outage; the only rows used as ground truth.
    """
    rows_in = len(raw)
    df = raw.drop_duplicates().copy()
    duplicates = rows_in - len(df)
    if df.duplicated(KEY).any():
        msg = "conflicting rows share (date, store_id, sku_id); not exact duplicates"
        raise ValueError(msg)

    df["sold"] = df["units_sold_full_price"] + df["units_sold_markdown"]

    blank = df["wastage_units"].isna()
    rebuilt = df["opening_stock"] + df["received_units"] - df["sold"] - df["closing_stock"]
    if (rebuilt[blank] < 0).any():
        msg = "stock arithmetic gives negative waste for a blank wastage row"
        raise ValueError(msg)
    df["waste_rebuilt"] = blank
    df["wastage_units"] = df["wastage_units"].where(~blank, rebuilt)

    residual = _balance(df, df["wastage_units"])
    outage = df["in_season"] & (df["sold"] == 0) & (residual > 0)
    df["outage"] = outage
    df["sold_corrected"] = df["sold"].where(~outage, df["sold"] + residual)
    df["usable_for_targets"] = df["in_season"] & ~outage

    leftover = _balance(df, df["wastage_units"])[~outage]
    if (leftover != 0).any():
        msg = f"{int((leftover != 0).sum())} rows still fail stock arithmetic after cleaning"
        raise ValueError(msg)

    df = df.sort_values(KEY).reset_index(drop=True)
    report = CleanReport(
        rows_in=rows_in,
        duplicates_removed=duplicates,
        blank_waste_rebuilt=int(blank.sum()),
        outage_rows=int(df["outage"].sum()),
        outage_store_days=int(
            df.loc[df["outage"], ["date", "store_id"]].drop_duplicates().shape[0]
        ),
        out_of_season_rows=int((~df["in_season"]).sum()),
        rows_out=len(df),
    )
    return CleanResult(data=df, report=report)
