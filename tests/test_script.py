"""Script-detection tests."""

from __future__ import annotations

from mfc.normalize.script import detect_script


def test_pure_malayalam() -> None:
    assert detect_script("ഇത് ഒരു മലയാളം വാചകം ആണ്") == "mlym"


def test_pure_latin() -> None:
    assert detect_script("This is an English sentence") == "latn"


def test_mixed_manglish() -> None:
    # Roughly half Latin, half Malayalam letters; below the 80% threshold either way.
    assert detect_script("ഇത് മലയാളം mixed text വാചകം") == "mixed"


def test_empty_returns_unknown() -> None:
    assert detect_script("") == "unknown"
    assert detect_script("12345 !@#") == "unknown"


def test_whitespace_and_digits_ignored() -> None:
    assert detect_script("hello 12345 world !@#") == "latn"
