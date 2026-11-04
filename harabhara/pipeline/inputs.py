"""Load the data pack once and derive the small tables the pipeline needs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from harabhara.data.clean import load_sheet
from harabhara.data.prepare import build_examples, build_panel
from harabhara.decisions.economics import unit_costs
from harabhara.decisions.surplus import Buyer, buyers_from_frame
from harabhara.settings.schema import AppConfig

SALES_FILE = "PS-10_store_sales_daily.xlsx"
EXTERNAL_FILE = "PS-10_external_factors.xlsx"
PROCUREMENT_FILE = "PS-10_procurement_and_inventory.xlsx"


@dataclass(frozen=True)
class PackData:
    cfg: AppConfig
    panel: pd.DataFrame
    examples: pd.DataFrame
    stores: pd.DataFrame
    skus: pd.DataFrame
    purchases: pd.DataFrame
    rules: pd.DataFrame
    transfers: pd.DataFrame
    fpo: pd.DataFrame
    buyers: list[Buyer]
    buyer_names: dict[str, str]
    snapshot_id: str


def snapshot_id(work_dir: Path) -> str:
    """A short fingerprint of the three data files, stored on every suggestion for replay."""
    digest = hashlib.sha256()
    for name in (SALES_FILE, EXTERNAL_FILE, PROCUREMENT_FILE):
        digest.update((work_dir / name).read_bytes())
    return f"pack-{digest.hexdigest()[:12]}"


def load_pack(work_dir: Path, cfg: AppConfig) -> PackData:
    sales, external, procurement = (
        work_dir / SALES_FILE,
        work_dir / EXTERNAL_FILE,
        work_dir / PROCUREMENT_FILE,
    )
    panel, _ = build_panel(sales, external, cfg)
    purchases = load_sheet(procurement, "purchases")
    purchases["date"] = pd.to_datetime(purchases["date"])
    buyer_frame = load_sheet(procurement, "surplus_buyers")
    transfers = load_sheet(procurement, "transfers")
    transfers["transfer_date"] = pd.to_datetime(transfers["transfer_date"])
    return PackData(
        cfg=cfg,
        panel=panel,
        examples=build_examples(panel, cfg),
        stores=load_sheet(sales, "stores"),
        skus=load_sheet(sales, "skus"),
        purchases=purchases,
        rules=load_sheet(procurement, "shelf_life_rules"),
        transfers=transfers,
        fpo=load_sheet(procurement, "fpo_contracts"),
        buyers=buyers_from_frame(buyer_frame),
        buyer_names={
            str(i): str(n)
            for i, n in zip(buyer_frame["buyer_id"], buyer_frame["name"], strict=True)
        },
        snapshot_id=snapshot_id(work_dir),
    )


def last_training_day(panel: pd.DataFrame) -> date:
    return pd.Timestamp(panel.loc[panel["split"] == "train", "date"].max()).date()


def life_days(rules: pd.DataFrame) -> dict[str, int]:
    """Sellable days at arrival per product: the grade A rule (docs/simulator.md)."""
    return {
        str(k): int(v)
        for k, v in rules.set_index("sku_id")["shelf_life_days_grade_A_ambient"].items()
    }


def unit_cost_by_sku(purchases: pd.DataFrame, upto: date) -> dict[str, float]:
    costs = unit_costs(purchases[purchases["date"] <= pd.Timestamp(upto)])
    return {str(k): float(v) for k, v in costs.items()}


def fpo_for_sku(fpo: pd.DataFrame) -> dict[str, str]:
    """Which farmer group supplies each product (products without a group are absent)."""
    mapping: dict[str, str] = {}
    for row in fpo.to_dict("records"):
        for sku in str(row["skus"]).split(","):
            mapping[sku.strip()] = str(row["fpo_id"])
    return mapping


def fpo_share_by_sku(purchases: pd.DataFrame, upto: date, days: int) -> dict[str, float]:
    """Share of each product's purchased volume that came from its farmer group, recent days."""
    window = purchases[
        (purchases["date"] <= pd.Timestamp(upto))
        & (purchases["date"] > pd.Timestamp(upto - timedelta(days=days)))
    ]
    total = window.groupby("sku_id")["quantity_units"].sum()
    fpo = window[window["source_type"] == "FPO contract"].groupby("sku_id")["quantity_units"].sum()
    share = (fpo / total).fillna(0.0)
    return {str(k): float(v) for k, v in share.items()}


def transfer_pairs(transfers: pd.DataFrame, upto: date) -> set[tuple[str, str]]:
    """Store pairs already seen in logged transfers: the only reach the pack can prove."""
    seen = transfers[transfers["transfer_date"] <= pd.Timestamp(upto)]
    return {(str(a), str(b)) for a, b in zip(seen["from_store"], seen["to_store"], strict=True)}
