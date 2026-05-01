"""schema.org ClaimReview JSON-LD extractor.

Primary path for IFCN sources. Uses ``extruct`` to pull all
``application/ld+json`` blocks, filters for ``@type == "ClaimReview"``,
and maps the standard fields onto :class:`ExtractResult`. Article body
(``evidence_text``) and the ``<link rel="canonical">`` URL are sourced
from the HTML directly via ``selectolax``, since ClaimReview itself does
not carry the debunking prose.
"""

from __future__ import annotations

from typing import Any

import extruct
from selectolax.parser import HTMLParser

from mfc.extract.base import ExtractResult


def extract_claimreview(
    html: str,
    url: str,
    *,
    body_selector: str | None = None,
    title_selector: str | None = None,
) -> ExtractResult | None:
    """Return an :class:`ExtractResult` if a ClaimReview block is present, else ``None``."""
    data = extruct.extract(html, base_url=url, syntaxes=["json-ld"], uniform=True)
    blocks: list[dict[str, Any]] = data.get("json-ld", []) or []

    review = _first_claimreview(blocks)
    if review is None:
        return None

    claim_text = _coerce_str(review.get("claimReviewed"))
    rating = _as_dict(review.get("reviewRating"))
    verdict_raw = _coerce_str(rating.get("alternateName") or rating.get("ratingValue"))
    published = _coerce_str(review.get("datePublished") or review.get("dateCreated"))
    title = _coerce_str(review.get("name") or review.get("headline"))
    language_raw = _coerce_str(review.get("inLanguage")) or None

    if not claim_text or not verdict_raw or not published:
        return None

    tree = HTMLParser(html)
    if not title and title_selector:
        title = _select_text(tree, title_selector)
    if not title:
        title = _select_text(tree, "h1") or url

    canonical = _canonical_url(tree)
    evidence_text = _select_text(tree, body_selector) if body_selector else ""

    has_full_payload = bool(evidence_text and title and canonical)
    confidence = 1.0 if has_full_payload else 0.7

    return ExtractResult(
        title=title,
        claim_text=claim_text,
        evidence_text=evidence_text,
        verdict_raw=verdict_raw,
        published_date_raw=published,
        language_raw=language_raw,
        url_canonical=canonical,
        extractor_used="claimreview_jsonld",
        extractor_confidence=confidence,
    )


def _first_claimreview(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for block in blocks:
        types = block.get("@type")
        if _matches_claimreview(types):
            return block
        graph = block.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict) and _matches_claimreview(node.get("@type")):
                    return node
    return None


def _matches_claimreview(types: Any) -> bool:
    if isinstance(types, str):
        return types == "ClaimReview"
    if isinstance(types, list):
        return "ClaimReview" in types
    return False


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list) and value:
        return _coerce_str(value[0])
    return str(value).strip()


def _select_text(tree: HTMLParser, selector: str) -> str:
    for raw in selector.split(","):
        css = raw.strip()
        if not css:
            continue
        node = tree.css_first(css)
        if node is not None:
            text = node.text(separator=" ", strip=True)
            if text:
                return text
    return ""


def _canonical_url(tree: HTMLParser) -> str | None:
    node = tree.css_first('link[rel="canonical"]')
    if node is None:
        return None
    href = node.attributes.get("href")
    return href.strip() if href else None
