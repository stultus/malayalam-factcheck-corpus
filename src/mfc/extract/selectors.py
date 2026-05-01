"""CSS-selector-based extractor.

Reads the per-source ``extraction.selectors`` block from the config JSON
and pulls the configured fields out of the page DOM via ``selectolax``.
Each selector entry is a comma-separated CSS list and the first match
wins. ``meta`` selectors read the ``content`` attribute; everything else
reads visible text. Returns ``None`` if either ``claim`` or ``verdict``
cannot be located, since both are mandatory for a usable record.
"""

from __future__ import annotations

from selectolax.parser import HTMLParser, Node

from mfc.extract.base import ExtractResult


def extract_selectors(
    html: str,
    url: str,
    selectors: dict[str, str | None],
) -> ExtractResult | None:
    tree = HTMLParser(html)

    claim_text = _select(tree, selectors.get("claim"))
    verdict_raw = _select(tree, selectors.get("verdict"))
    if not claim_text or not verdict_raw:
        return None

    title = _select(tree, selectors.get("title")) or _select(tree, "h1") or url
    evidence_text = _select(tree, selectors.get("content")) or ""
    published = _select(tree, selectors.get("published_date")) or ""
    canonical = _canonical_url(tree)

    has_full_payload = bool(evidence_text and title and canonical and published)
    confidence = 0.6 if has_full_payload else 0.4

    return ExtractResult(
        title=title,
        claim_text=claim_text,
        evidence_text=evidence_text,
        verdict_raw=verdict_raw,
        published_date_raw=published,
        language_raw=None,
        url_canonical=canonical,
        extractor_used="css_selectors",
        extractor_confidence=confidence,
    )


def _select(tree: HTMLParser, selector: str | None) -> str:
    if not selector:
        return ""
    for raw in selector.split(","):
        css = raw.strip()
        if not css:
            continue
        node = tree.css_first(css)
        if node is None:
            continue
        text = _node_value(node)
        if text:
            return text
    return ""


def _node_value(node: Node) -> str:
    if node.tag == "meta":
        content = node.attributes.get("content")
        return content.strip() if content else ""
    return node.text(separator=" ", strip=True)


def _canonical_url(tree: HTMLParser) -> str | None:
    node = tree.css_first('link[rel="canonical"]')
    if node is None:
        return None
    href = node.attributes.get("href")
    return href.strip() if href else None
