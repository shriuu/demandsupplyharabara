"""Store contacts: for the area manager only, never invented, and a bad number never loads."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harabhara.settings.contacts import StoreContact, load_contacts
from tests.backend.conftest import Env

V1 = "/api/v1"


def test_only_the_area_manager_can_read_contacts(env: Env) -> None:
    for pin, status in (("3333", 200), ("1111", 403), ("4444", 403), ("5555", 403)):
        r = env.client.get(f"{V1}/contacts", headers=env.login(pin))
        assert r.status_code == status, pin
    assert env.client.get(f"{V1}/contacts").status_code == 401


def test_the_shipped_numbers_are_clearly_dummy() -> None:
    rows = load_contacts()
    assert rows, "every store has a row"
    assert all(r.phone is None or r.phone.startswith("+91 90000 000") for r in rows)


def test_a_file_with_numbers_loads_and_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_contacts(tmp_path) == []
    row = "  S1: {name: Test, phone: '+91 98765 43210'}"
    (tmp_path / "contacts.yaml").write_text(f"stores:\n{row}\n")
    expected = StoreContact(store_id="S1", name="Test", phone="+91 98765 43210")
    assert load_contacts(tmp_path) == [expected]


@pytest.mark.parametrize("bad", ["call me", "tel:123456", "12", "+91-98765-43210; rm"])
def test_a_phone_that_is_not_digits_is_refused(bad: str) -> None:
    with pytest.raises(ValidationError):
        StoreContact(store_id="S1", phone=bad)
