"""Deterministic transaction dates preserve ISO days and legacy formats."""

from datetime import date

import pytest

from app.services.rag.exhaustive import _date


@pytest.mark.parametrize("day", [2, 5, 18, 29, 31])
def test_iso_transaction_date_preserves_day(day):
    assert _date(f"2026-07-{day:02}") == date(2026, 7, day)


@pytest.mark.parametrize(
    "value",
    ["31/07/2026", "31-07-2026", "31/07/26", "31-07-26", "31 Jul 2026", "31 Jul 26",
     " 2026-07-31 "],
)
def test_existing_transaction_date_formats(value):
    assert _date(value) == date(2026, 7, 31)


@pytest.mark.parametrize("value", ["2026-02-29", "2026-07-32", "2026-13-02", "2026-00-02", "2026-07-00"])
def test_invalid_iso_transaction_date_fails_closed(value):
    with pytest.raises(ValueError):
        _date(value)


def test_valid_iso_leap_day():
    assert _date("2024-02-29") == date(2024, 2, 29)
