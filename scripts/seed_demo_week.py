"""Fill the last week of the DEMO site with history, so every screen has something to show.

Synthetic data only. For each of the six days before today it:
- makes sure the evening orders of that day exist (builds the missing day with the real pipeline),
- records a decision on each order (mostly approved, some edited with a reason, a few rejected,
  a few left to run out of time), signed ``demo-seed`` so it is never mistaken for a real person,
- records each store's closing counts and the DC's purchases from the data pack's own rows for
  the data day that calendar day is mapped to (the same mapping the daily job uses).

Nothing is deleted or edited except the state of an order that had run out of time. The old
"ran out of time" audit event stays; the decision is added after it. A dry run is the default.

    uv run python -m scripts.seed_demo_week                 # show the plan, write nothing
    uv run python -m scripts.seed_demo_week --apply         # write to the live project
"""

from __future__ import annotations

import argparse
import contextlib
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from harabhara.api.firestore_store import FirestoreStorage
from harabhara.api.settings import from_env
from harabhara.api.storage import AlreadyExistsError, Storage
from harabhara.contracts import Approval, OrderPayload, OutcomeRecord, Suggestion
from harabhara.jobs.daily import pick_data_day
from harabhara.pipeline.forecast import fit_forecaster
from harabhara.pipeline.inputs import PackData, last_training_day, load_pack
from harabhara.pipeline.run import build_outputs, check_not_holdout, shift_to_today
from harabhara.settings.loader import load_config
from harabhara.workflow import audit

SEED = "demo-seed"
EDIT_REASON = "Demo data: adjusted for the day"
SHARE = (("approve", 72), ("edit", 16), ("reject", 7))  # the rest run out of time


def _roll(key: str) -> int:
    return zlib.crc32(key.encode()) % 100


def _choice(suggestion_id: str) -> str:
    n, edge = _roll(suggestion_id), 0
    for name, pct in SHARE:
        edge += pct
        if n < edge:
            return name
    return "leave"


def _edited(units: float, suggestion_id: str) -> float:
    swing = (zlib.crc32(("e" + suggestion_id).encode()) % 31 - 15) / 100  # -15% to +15%
    return max(0.0, round(units * (1 + swing)))


def _orders_of_day(storage: Storage, day: date) -> list[Suggestion]:
    tag = f"@demo{day:%Y%m%d}"
    return [
        s for s in storage.list_suggestions() if s.payload.kind == "order" and s.id.endswith(tag)
    ]


def _ensure_orders(
    storage: Storage, pack: PackData, day: date, data_day: date, tz: ZoneInfo, apply: bool
) -> list[Suggestion]:
    have = _orders_of_day(storage, day)
    if have:
        return have
    cfg = pack.cfg
    last = last_training_day(pack.panel)
    check_not_holdout(data_day, last)
    print(f"  {day}: no orders stored; building them for data day {data_day} (takes a few minutes)")
    out = build_outputs(pack, fit_forecaster(pack, data_day - timedelta(days=1)), data_day)
    now = datetime(day.year, day.month, day.day, 19, 30, tzinfo=tz)
    out = shift_to_today(
        out,
        day - data_day,
        f"demo{day:%Y%m%d}",
        now,
        cfg.modeling.pipeline.demo_keep_open_hours,
    )
    orders = [s for s in out.suggestions if s.payload.kind == "order"]
    if apply:
        for s in orders:
            with contextlib.suppress(AlreadyExistsError):
                storage.create_suggestion(s)
    return orders


def _decide(storage: Storage, s: Suggestion, tz: ZoneInfo, apply: bool) -> str:
    choice = _choice(s.id)
    if choice == "leave" or s.state not in ("proposed", "expired"):
        return "leave" if choice == "leave" else "kept"
    assert isinstance(s.payload, OrderPayload)
    minutes = 5 + zlib.crc32(("t" + s.id).encode()) % 40
    at = s.created_at + timedelta(minutes=minutes)
    new_state = {"approve": "approved", "edit": "edited", "reject": "rejected"}[choice]
    approval = Approval(
        suggestion_id=s.id,
        action=choice,
        actor_role="store_manager",
        actor_id=f"{SEED}:{s.store_id}",
        at=at.astimezone(tz),
        edited_units=_edited(s.payload.recommended_units, s.id) if choice == "edit" else None,
        reason=EDIT_REASON
        if choice == "edit"
        else ("Demo data: not needed" if choice == "reject" else None),
    )
    if apply and storage.transition(s.id, s.state, new_state):  # type: ignore[arg-type]
        with contextlib.suppress(AlreadyExistsError):
            storage.create_approval(approval)
            storage.append_audit(audit.decision(s, approval))
    return choice


def _wasted(row: pd.Series) -> float:
    """What the store recorded as thrown away; where that was blank, the rebuilt figure."""
    recorded = row["wastage_units"]
    return float(row["waste_rebuilt"] if recorded != recorded else recorded)


def _outcomes(pack: PackData, day: date, data_day: date, tz: ZoneInfo) -> list[OutcomeRecord]:
    at = datetime(day.year, day.month, day.day, 22, 30, tzinfo=tz)
    panel = pack.panel
    rows = panel[(panel["date"].dt.date == data_day) & (~panel["outage"].astype(bool))]
    records = [
        OutcomeRecord(
            kind="closing",
            on=day,
            store_id=str(r["store_id"]),
            sku_id=str(r["sku_id"]),
            units_sold=max(0.0, float(r["sold"])),
            units_wasted=max(0.0, float(_wasted(r))),
            sold_out=bool(r["stockout_flag"]),
            recorded_by=SEED,
            recorded_at=at,
        )
        for _, r in rows.iterrows()
        if r["sold"] == r["sold"] and _wasted(r) == _wasted(r)
    ]
    buys = pack.purchases[pack.purchases["date"].dt.date == data_day]
    for (sku, kind), grp in buys.groupby(["sku_id", "source_type"]):
        records.append(
            OutcomeRecord(
                kind="purchase",
                on=day,
                sku_id=str(sku),
                units_bought=float(grp["quantity_units"].sum()),
                source="farmer_group" if kind == "FPO contract" else "spot",
                recorded_by=SEED,
                recorded_at=at,
            )
        )
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to the live project")
    ap.add_argument("--work", default="work")
    ap.add_argument("--days", type=int, default=6, help="days before today to fill")
    ap.add_argument(
        "--nearest", type=int, default=1, help="fill from this many days back (1 = yesterday)"
    )
    ap.add_argument(
        "--outcomes-only",
        action="store_true",
        help="closing counts and purchases only: no orders are built or decided (older days)",
    )
    args = ap.parse_args()

    cfg = load_config()
    pack = load_pack(Path(args.work), cfg)
    tz = ZoneInfo(cfg.schedule.timezone)
    today = datetime.now(tz).date()
    last = last_training_day(pack.panel)
    window = cfg.modeling.pipeline.daily_demo_window_days
    storage = FirestoreStorage.from_project(from_env().firestore_project)
    print("APPLYING to the live project" if args.apply else "DRY RUN: nothing is written")

    for back in range(args.days, args.nearest - 1, -1):
        day = today - timedelta(days=back)
        data_day = pick_data_day(day, last, window)
        orders = (
            []
            if args.outcomes_only
            else _ensure_orders(storage, pack, day, data_day, tz, args.apply)
        )
        tally: dict[str, int] = {}
        for s in orders:
            what = _decide(storage, s, tz, args.apply)
            tally[what] = tally.get(what, 0) + 1
        records = _outcomes(pack, day, data_day, tz)
        if args.apply:
            for rec in records:
                storage.put_outcome(rec)
                with contextlib.suppress(AlreadyExistsError):
                    storage.append_audit(audit.outcome(rec))
        closings = sum(1 for r in records if r.kind == "closing")
        print(
            f"{day} (data day {data_day}): {len(orders)} orders {tally}; "
            f"{closings} closing rows, {len(records) - closings} purchase rows"
        )


if __name__ == "__main__":
    main()
