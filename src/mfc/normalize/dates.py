"""Parse mixed-format Indian site dates to UTC via dateparser.

Indian fact-check sites publish dates in IST-absolute, ISO 8601, relative
("2 hours ago"), and occasionally Malayalam-numeral form. ``dateparser``
handles the first three; Malayalam-numeral cases land in a later
iteration if the pilot turns up any.
"""

from __future__ import annotations

from datetime import UTC, datetime

import dateparser

_SETTINGS: dict[str, str | bool] = {
    "TIMEZONE": "Asia/Kolkata",
    "TO_TIMEZONE": "UTC",
    "RETURN_AS_TIMEZONE_AWARE": True,
}


def parse_date(value: str) -> datetime | None:
    """Return a UTC ``datetime`` or ``None`` if the input cannot be parsed."""
    cleaned = value.strip()
    if not cleaned:
        return None
    parsed = dateparser.parse(cleaned, languages=["ml", "en"], settings=_SETTINGS)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    result: datetime = parsed.astimezone(UTC)
    return result
