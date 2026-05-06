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

import re
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from selectolax.parser import HTMLParser

from mfc.fetch.client import FetchClient


@dataclass(frozen=True)
class PaginationSpec:
    """How to walk numbered pages of a category index."""

    query_param: str
    start: int = 2
    step: int = 1
    max_pages: int = 50


async def fetch_category_urls(
    client: FetchClient,
    page_urls: list[str],
    *,
    url_prefix: str | None = None,
    url_pattern: str | None = None,
    max_urls: int | None = None,
    headers: dict[str, str] | None = None,
    pagination: PaginationSpec | None = None,
) -> list[str]:
    """Return article URLs harvested from one or more category pages."""
    seen: set[str] = set()
    ordered: list[str] = []
    pattern = re.compile(url_pattern) if url_pattern else None

    def _absorb(html: str, base: str) -> int:
        added = 0
        for href in _extract_links(html, base):
            if url_prefix is not None and not href.startswith(url_prefix):
                continue
            if pattern is not None and not pattern.search(href):
                continue
            if href in seen:
                continue
            seen.add(href)
            ordered.append(href)
            added += 1
            if max_urls is not None and len(ordered) >= max_urls:
                break
        return added

    for page_url in page_urls:
        if max_urls is not None and len(ordered) >= max_urls:
            break
        response = await client.get(page_url, headers=headers)
        _absorb(response.text, page_url)
        if pagination is None:
            continue

        # Walk ?page=2, ?page=3, … until a page adds nothing new (the
        # listing has run out) or we hit max_pages. Stopping on
        # zero-additions is more robust than guessing the total count
        # since pagination DOM widgets vary across CMSes.
        for i in range(pagination.max_pages):
            if max_urls is not None and len(ordered) >= max_urls:
                break
            n = pagination.start + i * pagination.step
            paged_url = _with_query_param(page_url, pagination.query_param, n)
            paged = await client.get(paged_url, headers=headers)
            if _absorb(paged.text, paged_url) == 0:
                break

    return ordered


def _with_query_param(url: str, key: str, value: int) -> str:
    parsed = urlparse(url)
    existing = [kv for kv in parsed.query.split("&") if kv and not kv.startswith(f"{key}=")]
    existing.append(f"{key}={value}")
    return urlunparse(parsed._replace(query="&".join(existing)))


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
