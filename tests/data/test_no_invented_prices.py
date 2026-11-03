"""Guardrails 11 and 12 for the mandi feed: cited, cached, never invented. No network."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from harabhara.data.external import DiskCache, FeedError, MandiPriceClient
from harabhara.data.prices import PricePoint, price_shock
from harabhara.settings import load_config

FIXTURE = Path(__file__).parent / "fixtures" / "datagov_tomato.json"
CFG = load_config().feeds.mandi
NOW = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


class FakeHttp:
    def __init__(self, payload: Any = None, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail
        self.calls: list[dict[str, str]] = []
        self.headers: list[dict[str, str]] = []

    def get_json(
        self, url: str, params: dict[str, str], headers: dict[str, str], timeout_s: float
    ) -> Any:
        self.calls.append(params)
        self.headers.append(headers)
        if self.fail:
            msg = "boom"
            raise FeedError(msg)
        return self.payload


def tomato() -> Any:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def client(
    tmp_path: Path, http: FakeHttp, key: str | None = "k", now: datetime = NOW
) -> MandiPriceClient:
    return MandiPriceClient(
        CFG, http=http, cache=DiskCache(tmp_path), api_key=key, clock=lambda: now
    )


def test_ok_quote_is_cited_in_rupees_per_kg_and_prefers_first_market(tmp_path: Path) -> None:
    q = client(tmp_path, FakeHttp(tomato())).quote("P01", "Tomato")
    assert q.status == "ok"
    assert q.modal_inr == pytest.approx(
        25.0
    )  # Yeshwanthpur ranks above Binny Mill; 'Bangalore' NA row is dropped
    assert q.min_inr == pytest.approx(20.0)
    assert q.on == date(2026, 11, 3)
    assert "Ministry of Agriculture" in q.source


def test_request_is_gentle_and_identified(tmp_path: Path) -> None:
    http = FakeHttp(tomato())
    c = client(tmp_path, http)
    c.quote("P01", "Tomato")
    c.quote("P01", "Tomato")  # second call is served from the disk cache
    assert len(http.calls) == 1
    assert http.headers[0]["User-Agent"] == CFG.user_agent


def test_no_key_means_unavailable_with_no_price_and_no_request(tmp_path: Path) -> None:
    http = FakeHttp(tomato())
    q = client(tmp_path, http, key=None).quote("P01", "Tomato")
    assert q.status == "unavailable"
    assert q.modal_inr is None
    assert not http.calls
    assert q.source


def test_failure_without_cache_is_unavailable(tmp_path: Path) -> None:
    q = client(tmp_path, FakeHttp(fail=True)).quote("P01", "Tomato")
    assert q.status == "unavailable"
    assert q.modal_inr is None


@pytest.mark.parametrize("payload", [{}, {"records": []}, {"records": "x"}, [], None])
def test_empty_or_malformed_answer_is_unavailable(tmp_path: Path, payload: Any) -> None:
    q = client(tmp_path, FakeHttp(payload)).quote("P01", "Tomato")
    assert q.status == "unavailable"
    assert q.modal_inr is None


def test_unmapped_and_unverified_products_are_never_quoted(tmp_path: Path) -> None:
    http = FakeHttp(tomato())
    c = client(tmp_path, http)
    for product in ("Tender Coconut", "Dragon Fruit"):
        assert c.quote("P99", product).status == "unavailable"
    assert not http.calls
    assert "Tender Coconut" not in CFG.products


def test_failure_after_a_good_fetch_serves_the_cache_marked_stale(tmp_path: Path) -> None:
    client(tmp_path, FakeHttp(tomato())).quote("P01", "Tomato")
    later = NOW + timedelta(hours=CFG.stale_after_hours + 1)
    q = client(tmp_path, FakeHttp(fail=True), now=later).quote("P01", "Tomato")
    assert q.status == "stale"
    assert q.modal_inr == pytest.approx(25.0)
    assert q.fetched_at == NOW


def test_cache_between_ttl_and_stale_threshold_is_still_ok(tmp_path: Path) -> None:
    client(tmp_path, FakeHttp(tomato())).quote("P01", "Tomato")
    later = NOW + timedelta(hours=CFG.cache_ttl_hours + 1)
    q = client(tmp_path, FakeHttp(fail=True), now=later).quote("P01", "Tomato")
    assert q.status == "ok"


def test_cache_older_than_drop_threshold_is_not_shown(tmp_path: Path) -> None:
    client(tmp_path, FakeHttp(tomato())).quote("P01", "Tomato")
    later = NOW + timedelta(hours=CFG.drop_after_hours + 1)
    q = client(tmp_path, FakeHttp(fail=True), now=later).quote("P01", "Tomato")
    assert q.status == "unavailable"
    assert q.modal_inr is None


def test_price_dated_long_ago_is_stale_even_if_just_fetched(tmp_path: Path) -> None:
    payload = tomato()
    payload["records"] = [r for r in payload["records"] if r["arrival_date"] == "27/10/2026"]
    q = client(tmp_path, FakeHttp(payload)).quote("P01", "Tomato")
    assert q.status == "stale"
    assert q.on == date(2026, 10, 27)


def test_corrupt_cache_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "mandi_tomato.json").write_text("{not json", encoding="utf-8")
    q = client(tmp_path, FakeHttp(fail=True)).quote("P01", "Tomato")
    assert q.status == "unavailable"


def test_history_accumulates_for_the_shock_check(tmp_path: Path) -> None:
    c = client(tmp_path, FakeHttp(tomato()))
    c.quote("P01", "Tomato")
    hist = c.history("Tomato")
    assert [p.on for p in hist] == [date(2026, 10, 27), date(2026, 11, 3)]
    assert [p.modal_inr for p in hist] == pytest.approx([12.0, 25.0])
    shock = price_shock(
        hist,
        date(2026, 11, 3),
        lookback_days=CFG.price_shock.lookback_days,
        ratio_threshold=CFG.price_shock.ratio_threshold,
    )
    assert shock.flag == "up"
    assert shock.ratio == pytest.approx(25.0 / 12.0)


def test_the_key_never_appears_in_a_quote(tmp_path: Path) -> None:
    q = client(tmp_path, FakeHttp(tomato()), key="SECRET-KEY-123").quote("P01", "Tomato")
    assert "SECRET-KEY-123" not in q.model_dump_json()


# ---- price_shock ---------------------------------------------------------------------------

D = date(2026, 11, 3)


def pts(*pairs: tuple[int, float]) -> list[PricePoint]:
    return [PricePoint(on=D - timedelta(days=d), modal_inr=p) for d, p in pairs]


@pytest.mark.parametrize(
    ("history", "flag"),
    [
        (pts((0, 40), (7, 20)), "up"),  # doubled in a week (brief T5)
        (pts((0, 21), (7, 20)), "none"),
        (pts((0, 10), (7, 20)), "down"),
        (pts((0, 40)), "unknown"),  # nothing a week ago: do not guess
        (pts((7, 20)), "unknown"),  # nothing today
        (pts((0, 40), (7, 0)), "unknown"),
    ],
)
def test_price_shock_flags(history: list[PricePoint], flag: str) -> None:
    assert price_shock(history, D, lookback_days=7, ratio_threshold=1.5).flag == flag


def test_price_shock_uses_latest_earlier_price_and_says_which() -> None:
    s = price_shock(pts((0, 30), (9, 10), (12, 99)), D, lookback_days=7, ratio_threshold=1.5)
    assert s.past_on == D - timedelta(days=9)
    assert s.flag == "up"
