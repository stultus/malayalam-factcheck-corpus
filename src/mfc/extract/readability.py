"""Trafilatura-based readability fallback.

Last-resort extractor for pages where neither ClaimReview JSON-LD nor the
per-source CSS selectors find anything usable. Trafilatura recovers the
main article body and metadata, but it cannot tell which sentence is the
claim or which is the verdict, so this extractor:

- maps the page title onto ``claim_text`` (stripping ``Fact Check:`` style
  prefixes that many Malayalam outlets use), and
- leaves ``verdict_raw`` empty, so the normalize stage will record the
  record with ``verdict_canonical = "unknown"``.

These records reach the corpus tagged ``extractor_used = "readability"``
and ``extractor_confidence = 0.3`` — downstream training filters should
exclude them by default.
"""

from __future__ import annotations

import re

import trafilatura

from mfc.extract.base import ExtractResult

_TITLE_PREFIX = re.compile(
    r"^\s*(fact[\s-]*check|വസ്തുത\s*പരിശോധന)\s*[:\-\u2013]\s*",
    re.IGNORECASE,
)


def extract_readability(html: str, url: str) -> ExtractResult | None:
    body = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
    )
    if not body:
        return None

    metadata = trafilatura.extract_metadata(html, default_url=url)
    title = (metadata.title if metadata and metadata.title else "").strip()
    published = ""
    if metadata and metadata.date:
        published = metadata.date

    claim = _TITLE_PREFIX.sub("", title).strip() if title else ""
    if not claim:
        return None

    return ExtractResult(
        title=title or claim,
        claim_text=claim,
        evidence_text=body.strip(),
        verdict_raw="",
        published_date_raw=published,
        language_raw=None,
        url_canonical=None,
        extractor_used="readability",
        extractor_confidence=0.3,
    )
