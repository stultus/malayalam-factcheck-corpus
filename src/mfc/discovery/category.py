"""HTML category page to URL list.

For sources that publish a server-rendered index of fact-check articles
(e.g. Mathrubhumi, Manorama Online), this module fetches the configured
category page(s), extracts ``<a href>`` links, resolves them against the
page URL, and filters by an optional URL prefix so only article-section
URLs come back.

Single-page-app sites (Next.js App Router, etc.) hydrate their article
lists from streaming RSC payloads or XHR, and the static HTML carries
only chrome links. Those are out of scope here; they need a headless
browser or a site-specific API client.
"""

from __future__ import annotations

from urllib.parse import urldefrag, urljoin

from selectolax.parser import HTMLParser

from mfc.fetch.client import FetchClient


async def fetch_category_urls(
    client: FetchClient,
    page_urls: list[str],
    *,
    url_prefix: str | None = None,
    max_urls: int | None = None,
) -> list[str]:
    """Return article URLs harvested from one or more category pages."""
    seen: set[str] = set()
    ordered: list[str] = []

    for page_url in page_urls:
        if max_urls is not None and len(ordered) >= max_urls:
            break
        response = await client.get(page_url)
        for href in _extract_links(response.text, page_url):
            if url_prefix is not None and not href.startswith(url_prefix):
                continue
            if href in seen:
                continue
            seen.add(href)
            ordered.append(href)
            if max_urls is not None and len(ordered) >= max_urls:
                break

    return ordered


def _extract_links(html: str, page_url: str) -> list[str]:
    tree = HTMLParser(html)
    out: list[str] = []
    for anchor in tree.css("a[href]"):
        raw = (anchor.attributes.get("href") or "").strip()
        if not raw or raw.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute, _ = urldefrag(urljoin(page_url, raw))
        out.append(absolute)
    return out
