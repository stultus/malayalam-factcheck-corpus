"""Verdict canonicalisation tests."""

from __future__ import annotations

from mfc.normalize.labels import canonical_verdict

LOOKUP: dict[str, list[str]] = {
    "false": ["false", "fake", "വ്യാജം", "misleading claim", "incorrect"],
    "misleading": ["misleading", "missing context", "partly false", "half-true"],
    "true": ["true", "correct", "ശരിയാണ്"],
    "unverified": ["unverified", "unproven"],
    "satire": ["satire", "parody"],
}


def test_unknown_for_empty_string() -> None:
    assert canonical_verdict("", LOOKUP) == "unknown"
    assert canonical_verdict("   ", LOOKUP) == "unknown"


def test_unknown_for_unmatched_string() -> None:
    assert canonical_verdict("rumour", LOOKUP) == "unknown"


def test_longest_alias_wins_over_shorter_substring() -> None:
    # "misleading claim" (false) is longer than "misleading" (misleading)
    assert canonical_verdict("This is a misleading claim", LOOKUP) == "false"


def test_short_alias_when_only_match() -> None:
    assert canonical_verdict("Misleading", LOOKUP) == "misleading"


def test_malayalam_alias_match() -> None:
    assert canonical_verdict("വ്യാജം", LOOKUP) == "false"


def test_case_insensitive() -> None:
    assert canonical_verdict("FALSE", LOOKUP) == "false"
    assert canonical_verdict("True", LOOKUP) == "true"
