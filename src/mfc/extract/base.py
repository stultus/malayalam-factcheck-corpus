"""Extractor protocol.

Each extractor parses a fetched HTML page and returns an
:class:`ExtractResult` containing raw, source-specific field values (plus a
self-rated confidence). The normalize stage maps these raw values onto the
canonical :class:`FactCheckRecord`.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ExtractResult(BaseModel):
    """Raw fields extracted from a single fact-check article."""

    model_config = ConfigDict(extra="forbid")

    title: str
    claim_text: str
    evidence_text: str
    verdict_raw: str
    published_date_raw: str
    language_raw: str | None = None
    url_canonical: str | None = None
    extractor_used: str
    extractor_confidence: float


class Extractor(Protocol):
    """Returns an :class:`ExtractResult` or ``None`` if the strategy doesn't apply."""

    def extract(self, html: str, url: str) -> ExtractResult | None: ...
