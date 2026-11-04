"""Write the one-sentence reason a manager would say (guardrail 9, CLAUDE.md s6).

A reason is built only from the suggestion's own drivers: the real facts behind it, such as a
heavy-rain forecast or a last sellable day. Each driver code has a fixed phrase in
``templates/en.yaml``; a driver with no phrase is never mentioned. Nothing is invented, and a
language model may only reword the sentence this writes, never replace it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from harabhara.contracts import (
    Driver,
    MarkdownPayload,
    OrderPayload,
    Payload,
    SurplusPayload,
    TransferPayload,
)

TEMPLATES = Path(__file__).parent / "templates"


class NoReasonError(ValueError):
    """No honest one-sentence reason can be written. The suggestion must not be shown."""


@dataclass(frozen=True)
class Names:
    """Display names for ids, so a sentence reads like speech."""

    product: str
    unit: str
    stores: Mapping[str, str]
    buyers: Mapping[str, str]


@cache
def load_templates(language: str = "en") -> dict[str, Any]:
    loaded = yaml.safe_load((TEMPLATES / f"{language}.yaml").read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        msg = f"template file for {language!r} must be a mapping"
        raise TypeError(msg)
    return loaded


def known_codes(language: str = "en") -> frozenset[str]:
    """Driver codes the writer can turn into words."""
    return frozenset(load_templates(language)["phrases"])


def _n(value: float) -> str:
    return str(round(value)) if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def _opener(payload: Payload, store_id: str, names: Names, templates: Mapping[str, Any]) -> str:
    openers = templates["openers"]
    store = names.stores.get(store_id, store_id)
    common = {"product": names.product, "unit": names.unit, "store": store}
    if isinstance(payload, OrderPayload):
        return str(openers["order"].format(units=_n(payload.recommended_units), **common))
    if isinstance(payload, MarkdownPayload):
        return str(
            openers["markdown"].format(
                units=_n(payload.units), pct=_n(payload.step_pct), start=payload.start, **common
            )
        )
    if isinstance(payload, TransferPayload):
        return str(
            openers["transfer"].format(
                units=_n(payload.units),
                product=names.product,
                unit=names.unit,
                from_store=names.stores.get(payload.from_store, payload.from_store),
                to_store=names.stores.get(payload.to_store, payload.to_store),
                leave_by=payload.leave_by,
            )
        )
    if isinstance(payload, SurplusPayload):
        if payload.price_share_of_retail is not None and payload.profit_vs_cost_inr is not None:
            gain = payload.profit_vs_cost_inr
            return str(
                openers["surplus_priced"].format(
                    units=_n(payload.units),
                    product=names.product,
                    unit=names.unit,
                    buyer=names.buyers.get(payload.buyer_id, payload.buyer_id),
                    window=payload.pickup_window,
                    share=_n(payload.price_share_of_retail * 100),
                    amount=_n(abs(gain)),
                    versus=templates["versus"]["above" if gain >= 0 else "below"],
                )
            )
        return str(
            openers["surplus"].format(
                units=_n(payload.units),
                product=names.product,
                unit=names.unit,
                buyer=names.buyers.get(payload.buyer_id, payload.buyer_id),
                window=payload.pickup_window,
            )
        )
    msg = f"no opener for {type(payload).__name__}"
    raise NoReasonError(msg)


def _phrases(drivers: Sequence[Driver], templates: Mapping[str, Any]) -> list[str]:
    """Codes that have words, thin-history warnings first, otherwise in the given order."""
    phrases: Mapping[str, str] = templates["phrases"]
    priority: Sequence[str] = templates["first"]
    codes: list[str] = []
    for d in drivers:
        if d.code in phrases and d.code not in codes:
            codes.append(d.code)
    codes.sort(key=lambda c: 0 if c in priority else 1)  # stable: keeps the given order
    return [phrases[c] for c in codes]


def write_reason(
    *,
    payload: Payload,
    drivers: Sequence[Driver],
    store_id: str,
    names: Names,
    max_chars: int,
    language: str = "en",
) -> str:
    """One sentence for this suggestion, or ``NoReasonError`` if it cannot be written honestly."""
    templates = load_templates(language)
    phrases = _phrases(drivers, templates)
    if not phrases:
        msg = "none of the drivers has a phrase, so there is no honest reason to give"
        raise NoReasonError(msg)
    opener = _opener(payload, store_id, names, templates)
    for count in (2, 1):
        body = str(templates["joiner"]).join(phrases[:count])
        sentence = f"{opener}{templates['connector']}{body}."
        if len(sentence) <= max_chars:
            return sentence
    msg = "the sentence would be too long to read at a glance"
    raise NoReasonError(msg)
