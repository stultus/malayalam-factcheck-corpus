"""Runs extractors in priority order. First success wins.

JSON-LD ``ClaimReview`` is the primary path for IFCN sources. When that
returns ``None``, the per-source CSS selector block from the config takes
over. The trafilatura readability fallback lands in a later iteration.
"""

from __future__ import annotations

from mfc.config import SourceConfig
from mfc.extract.base import ExtractResult
from mfc.extract.claimreview import extract_claimreview
from mfc.extract.selectors import extract_selectors


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

    if selectors:
        result = extract_selectors(html, url, selectors)
        if result is not None:
            return result

    return None
