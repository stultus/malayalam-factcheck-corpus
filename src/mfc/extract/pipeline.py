"""Runs extractors in priority order. First success wins.

JSON-LD ``ClaimReview`` is the primary path for IFCN sources. When that
returns ``None``, the per-source CSS selector block from the config takes
over. Trafilatura's readability extractor is the last-resort fallback for
pages where neither structured path succeeds; the resulting records carry
``extractor_used = "readability"``, ``verdict_canonical = "unknown"``,
and a low confidence score so downstream filters can exclude them.
"""

from __future__ import annotations

from mfc.config import SourceConfig
from mfc.extract.base import ExtractResult
from mfc.extract.claimreview import extract_claimreview
from mfc.extract.readability import extract_readability
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

    return extract_readability(html, url)
