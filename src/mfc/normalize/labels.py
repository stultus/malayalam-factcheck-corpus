"""Map raw verdict strings to canonical labels via the config's lookup table.

Matching is case-insensitive: an alias matches if it appears as a substring
of the publisher's verdict string. The longest alias wins, so a more
specific phrase (e.g. ``"misleading claim"`` under ``false``) beats a
shorter one (e.g. ``"misleading"`` under ``misleading``). Unknown verdicts
return ``"unknown"`` and the record gets flagged for manual review later.
"""

from __future__ import annotations

from typing import cast, get_args

from mfc.corpus.record import VerdictCanonical

CANONICAL_VALUES: tuple[str, ...] = get_args(VerdictCanonical)


def canonical_verdict(
    verdict_raw: str,
    lookup: dict[str, list[str]],
) -> VerdictCanonical:
    """Return the canonical label for ``verdict_raw`` or ``"unknown"``."""
    needle = verdict_raw.strip().lower()
    if not needle:
        return "unknown"

    best: tuple[int, VerdictCanonical] | None = None
    for canonical, aliases in lookup.items():
        if canonical not in CANONICAL_VALUES:
            continue
        for alias in aliases:
            alias_lower = alias.lower()
            if not alias_lower or alias_lower not in needle:
                continue
            if best is None or len(alias_lower) > best[0]:
                best = (len(alias_lower), cast(VerdictCanonical, canonical))
    return best[1] if best else "unknown"
