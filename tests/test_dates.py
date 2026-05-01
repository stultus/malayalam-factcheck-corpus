"""Date parsing tests."""

from __future__ import annotations

from datetime import UTC

from mfc.normalize.dates import parse_date


def test_iso_8601_with_offset() -> None:
    parsed = parse_date("2026-04-20T15:30:00+05:30")
    assert parsed is not None
    assert parsed.tzinfo == UTC
    assert parsed.year == 2026
    assert parsed.hour == 10  # 15:30 IST -> 10:00 UTC


def test_naive_date_treated_as_ist() -> None:
    parsed = parse_date("2026-04-20 12:00:00")
    assert parsed is not None
    assert parsed.tzinfo == UTC
    # 12:00 IST = 06:30 UTC
    assert parsed.hour == 6
    assert parsed.minute == 30


def test_empty_returns_none() -> None:
    assert parse_date("") is None
    assert parse_date("   ") is None


def test_garbage_returns_none() -> None:
    assert parse_date("not a date") is None
