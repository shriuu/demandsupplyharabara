"""The reason writer: one sentence, from real drivers only, within the limit."""

from __future__ import annotations

import re
from itertools import combinations
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harabhara.contracts import Driver
from harabhara.reasons.writer import Names, NoReasonError, known_codes, load_templates, write_reason
from harabhara.rules.engine import RulesEngine
from harabhara.settings import AppConfig
from tests.rules.conftest import good_facts, markdown, order, suggestion, surplus, transfer

NAMES = Names(
    product="tomatoes",
    unit="kg",
    stores={"S01": "Jayanagar", "S02": "Indiranagar"},
    buyers={"B1": "Prime Pickle"},
)
MAX = 200


def _drivers(*codes: str) -> list[Driver]:
    return [Driver(kind="rule", direction="none", code=c) for c in codes]


def _write(payload: Any, *codes: str, max_chars: int = MAX) -> str:
    return write_reason(
        payload=payload, drivers=_drivers(*codes), store_id="S01", names=NAMES, max_chars=max_chars
    )


@pytest.mark.parametrize(
    ("payload", "must_contain"),
    [
        (order(), ["Order 40 kg of tomatoes for Jayanagar"]),
        (markdown(), ["Mark down 20 kg of tomatoes by 30% from 07:00"]),
        (transfer(), ["Move 25 kg of tomatoes from Jayanagar to Indiranagar", "09:30"]),
        (surplus(), ["Offer 30 kg of tomatoes to Prime Pickle", "21:00-23:00"]),
    ],
)
def test_each_kind_gives_one_sentence_with_the_real_numbers(
    payload: Any, must_contain: list[str]
) -> None:
    text = _write(payload, "last_day")
    assert text.endswith(".")
    assert "\n" not in text
    assert text.count(". ") == 0
    for part in must_contain:
        assert part in text
    assert "because it is on its last sellable day" in text


def test_only_the_given_drivers_are_used_never_invented() -> None:
    text = _write(markdown(), "last_day")
    assert "rain" not in text
    assert "festival" not in text
    assert "weekend" not in text


def test_a_driver_without_words_is_ignored_and_none_at_all_means_no_reason() -> None:
    assert "last sellable day" in _write(markdown(), "not_a_known_code", "last_day")
    with pytest.raises(NoReasonError):
        _write(markdown(), "not_a_known_code")
    with pytest.raises(NoReasonError):
        _write(markdown())


def test_thin_history_is_always_said_first() -> None:
    text = _write(order(), "weekend", "heavy_rain_walk_in", "thin_history")
    assert text.index("little history") < text.index("weekend")


def test_at_most_two_reasons_are_given() -> None:
    text = _write(order(), "weekend", "hot_day", "sold_out_yesterday")
    assert text.count(" and ") == 1


def test_a_second_reason_is_dropped_before_the_sentence_gets_too_long() -> None:
    both = _write(order(), "festival_eve", "sold_out_yesterday")
    one = _write(order(), "festival_eve", "sold_out_yesterday", max_chars=len(both) - 1)
    assert len(one) < len(both)
    assert "sold out yesterday" not in one


def test_a_sentence_that_cannot_fit_is_refused_not_cut_short() -> None:
    with pytest.raises(NoReasonError):
        _write(order(), "festival_eve", max_chars=30)


def test_every_phrase_and_opener_is_clean_and_complete() -> None:
    templates = load_templates()
    for code, phrase in templates["phrases"].items():
        assert phrase.strip() == phrase, code
        assert "\n" not in phrase, code
        assert "{" not in phrase, code
        assert not phrase.endswith("."), code  # the writer adds the full stop
        assert phrase == phrase[0].lower() + phrase[1:], code
    for kind, opener in templates["openers"].items():
        assert opener[0].isupper(), kind
        assert not opener.endswith("."), kind
    assert set(templates["first"]) <= set(templates["phrases"])


def test_every_known_code_works_with_every_kind_and_fits_the_limit(cfg: AppConfig) -> None:
    limit = cfg.rules.explanations.max_reason_chars
    for code in sorted(known_codes()):
        for payload in (order(), markdown(), transfer(), surplus()):
            text = write_reason(
                payload=payload,
                drivers=_drivers(code),
                store_id="S01",
                names=NAMES,
                max_chars=limit,
            )
            assert len(text) <= limit, (code, type(payload).__name__)


@given(codes=st.lists(st.sampled_from(sorted(known_codes())), min_size=1, max_size=3, unique=True))
def test_whatever_the_drivers_the_sentence_passes_the_guardrail(codes: list[str]) -> None:
    from harabhara.settings import load_config

    cfg = load_config()
    text = write_reason(
        payload=markdown(), drivers=_drivers(*codes), store_id="S01", names=NAMES,
        max_chars=cfg.rules.explanations.max_reason_chars,
    )  # fmt: skip
    s = suggestion(markdown(), reason=text, drivers=_drivers(*codes))
    verdict = RulesEngine(cfg).evaluate(s, good_facts(thin_history="thin_history" in codes))
    assert not [v for v in verdict.violations if v.rule in {"G09", "G10"}]


def test_every_phrase_in_a_sentence_traces_back_to_a_driver_that_was_given() -> None:
    phrases: dict[str, str] = load_templates()["phrases"]
    given_codes = ["weekend", "heavy_rain_walk_in"]
    text = _write(order(), *given_codes)
    mentioned = [code for code, phrase in phrases.items() if phrase in text]
    assert set(mentioned) == set(given_codes)


def test_no_two_codes_share_the_same_words() -> None:
    phrases = list(load_templates()["phrases"].values())
    assert len(phrases) == len(set(phrases))
    for a, b in combinations(phrases, 2):
        assert not re.fullmatch(re.escape(a), b)
