"""CSS-selector-based extractor.

Reads the per-source ``extraction.selectors`` block from the config JSON
and pulls the configured fields out of the page DOM via ``selectolax``.
Each selector entry is a comma-separated CSS list and the first match
wins. ``meta`` selectors read the ``content`` attribute; everything else
reads visible text. Returns ``None`` if either ``claim`` or ``verdict``
cannot be located, since both are mandatory for a usable record.

If the configured ``verdict`` selector misses, falls back to scanning
body paragraphs for a ``Result: <verdict>`` summary line. This is the
convention used by Fact Crescendo English (and similar layouts) to mark
the verdict at the end of the article without a dedicated CSS class.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from mfc.extract.base import ExtractResult

_RESULT_LINE = re.compile(r"^\s*Result\s*:\s*(.+?)\s*$", re.IGNORECASE)


def extract_selectors(
    html: str,
    url: str,
    selectors: dict[str, str | None],
) -> ExtractResult | None:
    tree = HTMLParser(html)
    _strip_non_content(tree)

    claim_text = _select(tree, selectors.get("claim"))
    verdict_raw = _select(tree, selectors.get("verdict"))
    if not verdict_raw:
        verdict_raw = _result_line_fallback(tree, selectors.get("content"))
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


def _strip_non_content(tree: HTMLParser) -> None:
    # selectolax's Node.text() concatenates descendant text including
    # <style>/<script>/<noscript> bodies, so inline CSS rules and JS
    # leak into the visible text. Decompose them up front so every
    # subsequent _select() returns clean prose.
    for node in tree.css("script, style, noscript, template"):
        node.decompose()


def _canonical_url(tree: HTMLParser) -> str | None:
    node = tree.css_first('link[rel="canonical"]')
    if node is None:
        return None
    href = node.attributes.get("href")
    return href.strip() if href else None


def _result_line_fallback(tree: HTMLParser, content_selector: str | None) -> str:
    container: Node | None = None
    if content_selector:
        for raw in content_selector.split(","):
            css = raw.strip()
            if not css:
                continue
            container = tree.css_first(css)
            if container is not None:
                break
    if container is None:
        container = tree.body
    if container is None:
        return ""
    for p in container.css("p"):
        match = _RESULT_LINE.match(p.text(separator=" ", strip=True))
        if match:
            return match.group(1).strip()
    return ""
