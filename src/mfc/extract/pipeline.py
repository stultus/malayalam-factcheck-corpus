"""Runs extractors in priority order. First success wins.

For the pilot, only the ClaimReview JSON-LD extractor is wired up. The
selectors and readability fallbacks land in a later iteration.
"""

from __future__ import annotations

from mfc.config import SourceConfig
from mfc.extract.base import ExtractResult
from mfc.extract.claimreview import extract_claimreview


def run_extractors(html: str, url: str, source: SourceConfig) -> ExtractResult | None:
    selectors = source.extraction.selectors
    body_selector = selectors.get("content")
    title_selector = selectors.get("title")

    if source.extraction.claimreview_jsonld:
        result = extract_claimreview(
            html,
            url,
            body_selector=body_selector,
            title_selector=title_selector,
        )
        if result is not None:
            return result

    return None
