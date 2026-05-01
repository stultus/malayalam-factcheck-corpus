"""XML sitemap to URL list.

Walks a ``<sitemapindex>`` recursively into its child ``<urlset>`` documents
and returns article URLs in document order. The optional ``url_prefix``
filter restricts results to a single section of the site (e.g.
``https://newschecker.in/ml/``), so a multi-language portal's full sitemap
can be sampled without crawling unrelated content.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from mfc.fetch.client import FetchClient

_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


async def fetch_sitemap_urls(
    client: FetchClient,
    sitemap_url: str,
    *,
    url_prefix: str | None = None,
    url_pattern: str | None = None,
    max_urls: int | None = None,
    headers: dict[str, str] | None = None,
) -> list[str]:
    """Return article URLs from a sitemap or sitemap index, optionally filtered."""
    collected: list[str] = []
    pattern = re.compile(url_pattern) if url_pattern else None
    await _walk(client, sitemap_url, url_prefix, pattern, max_urls, headers, collected)
    return collected


async def _walk(
    client: FetchClient,
    sitemap_url: str,
    url_prefix: str | None,
    url_pattern: re.Pattern[str] | None,
    max_urls: int | None,
    headers: dict[str, str] | None,
    collected: list[str],
) -> None:
    if max_urls is not None and len(collected) >= max_urls:
        return

    response = await client.get(sitemap_url, headers=headers)
    root = ET.fromstring(response.text)
    tag = root.tag

    if tag == f"{_SM_NS}sitemapindex":
        for sm in root.findall(f"{_SM_NS}sitemap"):
            loc = sm.findtext(f"{_SM_NS}loc")
            if not loc:
                continue
            await _walk(client, loc.strip(), url_prefix, url_pattern, max_urls, headers, collected)
            if max_urls is not None and len(collected) >= max_urls:
                return
        return

    if tag == f"{_SM_NS}urlset":
        for url_el in root.findall(f"{_SM_NS}url"):
            loc = url_el.findtext(f"{_SM_NS}loc")
            if not loc:
                continue
            href = loc.strip()
            if url_prefix is not None and not href.startswith(url_prefix):
                continue
            if url_pattern is not None and not url_pattern.search(href):
                continue
            collected.append(href)
            if max_urls is not None and len(collected) >= max_urls:
                return
