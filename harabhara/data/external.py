"""Live public mandi prices from data.gov.in (Agmarknet), cited, cached, and never invented.

Guardrail 11: every quote carries its citation; a price that is missing is ``unavailable`` with
no number. Guardrail 12: any failure degrades to the disk cache (marked stale) or to nothing.
Real prices are for display only; the demand model keeps training on the pack's prices.
The API key is read from the environment by the caller and is never logged or put in an error.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib import error, parse, request

from pydantic import BaseModel, ConfigDict, ValidationError

from harabhara.contracts import PriceQuote
from harabhara.data.prices import PricePoint
from harabhara.settings.schema import Mandi

UNAVAILABLE_SOURCE_SUFFIX = " (no price available)"


class FeedError(RuntimeError):
    """The feed could not be read. The message never contains the URL or the key."""


class HttpClient(Protocol):
    def get_json(
        self, url: str, params: dict[str, str], headers: dict[str, str], timeout_s: float
    ) -> Any: ...


class UrllibHttp:
    """Plain standard-library HTTP so the feed adds no dependency."""

    def get_json(
        self, url: str, params: dict[str, str], headers: dict[str, str], timeout_s: float
    ) -> Any:
        full = f"{url}?{parse.urlencode(params)}"
        req = request.Request(full, headers=headers)
        try:
            with request.urlopen(req, timeout=timeout_s) as resp:
                return json.loads(resp.read())
        except error.HTTPError as exc:
            msg = f"feed answered HTTP {exc.code}"
            raise FeedError(msg) from None
        except (error.URLError, TimeoutError, OSError, ValueError):
            msg = "feed could not be reached or sent unreadable data"
            raise FeedError(msg) from None


class MandiRecord(BaseModel):
    """One market's prices for one commodity on one day, in Rs per kg."""

    model_config = ConfigDict(frozen=True)

    on: date
    market: str
    min_inr: float | None
    max_inr: float | None
    modal_inr: float


@dataclass(frozen=True)
class _Cached:
    fetched_at: datetime
    records: list[MandiRecord]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _rank(market: str, markets: list[str]) -> int | None:
    """Position of the first configured market named inside the feed's market name."""
    name = _norm(market)
    return next((i for i, m in enumerate(markets) if _norm(m) in name), None)


def _num(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def parse_records(
    payload: Any, *, kg_per_quintal: float, commodity: str, markets: list[str]
) -> list[MandiRecord]:
    """Turn a data.gov.in response into records; rows that are unreadable are dropped."""
    rows = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        msg = "feed response has no records list"
        raise FeedError(msg)
    out: list[MandiRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        low = {str(k).lower(): v for k, v in row.items()}
        if _norm(str(low.get("commodity", ""))) != _norm(commodity):
            continue
        market = str(low.get("market", "")).strip()
        if _rank(market, markets) is None:
            continue
        modal = _num(low.get("modal_price"))
        try:
            on = datetime.strptime(str(low.get("arrival_date")), "%d/%m/%Y").date()
        except ValueError:
            continue
        if modal is None or modal == 0:
            continue
        lo, hi = _num(low.get("min_price")), _num(low.get("max_price"))
        out.append(
            MandiRecord(
                on=on,
                market=market,
                min_inr=None if lo is None else lo / kg_per_quintal,
                max_inr=None if hi is None else hi / kg_per_quintal,
                modal_inr=modal / kg_per_quintal,
            )
        )
    return out


class DiskCache:
    """One small JSON file per commodity; keeps a short price history for the shock check."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def _path(self, commodity: str) -> Path:
        return self._dir / f"mandi_{_norm(commodity)}.json"

    def load(self, commodity: str) -> _Cached | None:
        try:
            raw = json.loads(self._path(commodity).read_text(encoding="utf-8"))
            return _Cached(
                fetched_at=datetime.fromisoformat(raw["fetched_at"]),
                records=[MandiRecord.model_validate(r) for r in raw["records"]],
            )
        except (OSError, ValueError, KeyError, TypeError, ValidationError):
            return None  # a missing or corrupt cache is the same as no cache

    def save(self, commodity: str, fetched_at: datetime, records: list[MandiRecord]) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            body = {
                "fetched_at": fetched_at.isoformat(),
                "records": [r.model_dump(mode="json") for r in records],
            }
            self._path(commodity).write_text(json.dumps(body), encoding="utf-8")
        except OSError:
            return  # cache is an optimisation; failing to write must not fail the quote


def _merge(
    old: list[MandiRecord], new: list[MandiRecord], today: date, keep_days: int
) -> list[MandiRecord]:
    by_key = {(r.on, _norm(r.market)): r for r in old}
    by_key.update({(r.on, _norm(r.market)): r for r in new})
    cutoff = today - timedelta(days=keep_days)
    return sorted((r for r in by_key.values() if r.on >= cutoff), key=lambda r: (r.on, r.market))


class MandiPriceClient:
    """Quotes for the products named in config; one gentle request per commodity per TTL."""

    def __init__(
        self,
        cfg: Mandi,
        *,
        http: HttpClient,
        cache: DiskCache,
        api_key: str | None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._cfg = cfg
        self._http = http
        self._cache = cache
        self._key = api_key
        self._clock = clock

    # ---- public -------------------------------------------------------------------------

    def quote(self, sku_id: str, product: str) -> PriceQuote:
        """Latest modal price (Rs per kg) for ``product``, or ``unavailable`` with no price."""
        now = self._clock()
        commodity = self._cfg.products.get(product)
        if commodity is None:
            return self._unavailable(sku_id, now, "product has no verified feed mapping")
        cached = self._cache.load(commodity)
        fresh = cached is not None and now - cached.fetched_at <= timedelta(
            hours=self._cfg.cache_ttl_hours
        )
        if not fresh:
            cached = self._refresh(commodity, cached, now) or cached
        return self._quote_from(sku_id, cached, now)

    def history(self, product: str) -> list[PricePoint]:
        """Cached daily modal prices (first configured market that has each day)."""
        commodity = self._cfg.products.get(product)
        cached = self._cache.load(commodity) if commodity else None
        if cached is None:
            return []
        points: dict[date, float] = {}
        for r in sorted(cached.records, key=lambda r: _rank(r.market, self._cfg.markets) or 0):
            points.setdefault(r.on, r.modal_inr)
        return [PricePoint(on=d, modal_inr=p) for d, p in sorted(points.items())]

    # ---- internals ----------------------------------------------------------------------

    def _source(self) -> str:
        return f"{self._cfg.citation} Prices in Rs per kg, converted from Rs per quintal."

    def _unavailable(self, sku_id: str, now: datetime, why: str) -> PriceQuote:
        return PriceQuote(
            sku_id=sku_id,
            market=self._cfg.markets[0],
            on=now.date(),
            source=f"{self._cfg.citation}{UNAVAILABLE_SOURCE_SUFFIX}: {why}",
            fetched_at=now,
            status="unavailable",
        )

    def _refresh(self, commodity: str, cached: _Cached | None, now: datetime) -> _Cached | None:
        if not self._key:
            return None
        params = {
            "api-key": self._key,
            "format": "json",
            "limit": str(self._cfg.page_limit),
            "filters[state.keyword]": self._cfg.state,
            "filters[district.keyword]": self._cfg.district,
            "filters[commodity]": commodity,
        }
        url = f"{self._cfg.base_url}/{self._cfg.resource_id}"
        headers = {"User-Agent": self._cfg.user_agent, "Accept": "application/json"}
        try:
            payload = self._http.get_json(url, params, headers, self._cfg.timeout_s)
            fresh = parse_records(
                payload,
                kg_per_quintal=self._cfg.kg_per_quintal,
                commodity=commodity,
                markets=self._cfg.markets,
            )
        except FeedError:
            return None
        if not fresh:
            return None  # an empty answer is not evidence of a price
        merged = _merge(
            cached.records if cached else [], fresh, now.date(), self._cfg.history_keep_days
        )
        self._cache.save(commodity, now, merged)
        return _Cached(fetched_at=now, records=merged)

    def _quote_from(self, sku_id: str, cached: _Cached | None, now: datetime) -> PriceQuote:
        if cached is None or not cached.records:
            why = "no key set" if not self._key else "feed unavailable and no cached price"
            return self._unavailable(sku_id, now, why)
        age = now - cached.fetched_at
        if age > timedelta(hours=self._cfg.drop_after_hours):
            return self._unavailable(sku_id, now, "cached price is too old to show")
        latest_day = max(r.on for r in cached.records)
        today_rows = [r for r in cached.records if r.on == latest_day]
        pick = min(today_rows, key=lambda r: _rank(r.market, self._cfg.markets) or 0)
        too_old = (now.date() - latest_day) > timedelta(days=self._cfg.price_max_age_days)
        stale = age > timedelta(hours=self._cfg.stale_after_hours) or too_old
        return PriceQuote(
            sku_id=sku_id,
            market=pick.market,
            on=pick.on,
            modal_inr=pick.modal_inr,
            min_inr=pick.min_inr,
            max_inr=pick.max_inr,
            source=self._source(),
            fetched_at=cached.fetched_at,
            status="stale" if stale else "ok",
        )
