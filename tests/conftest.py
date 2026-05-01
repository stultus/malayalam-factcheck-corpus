"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FACTCRESCENDO_ML_DIR = FIXTURES_DIR / "html" / "factcrescendo_ml"


@pytest.fixture
def factcrescendo_ml_pages() -> list[tuple[str, str]]:
    """Return ``(stem, html)`` pairs for every committed FC Malayalam fixture."""
    pages: list[tuple[str, str]] = []
    for path in sorted(FACTCRESCENDO_ML_DIR.glob("*.html")):
        pages.append((path.stem, path.read_text(encoding="utf-8")))
    return pages
