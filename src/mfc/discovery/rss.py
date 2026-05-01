"""RSS feed to URL list.

Parses an RSS 2.0 or Atom feed and returns the article URLs in publication
order (newest first, as the feed itself orders them). The feed is fetched
through :class:`mfc.fetch.client.FetchClient` so robots.txt and rate limits
still apply.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from mfc.fetch.client import FetchClient

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


async def fetch_rss_urls(client: FetchClient, feed_url: str) -> list[str]:
    """Return article URLs from an RSS or Atom feed."""
    response = await client.get(feed_url)
    return _parse(response.text)


def _parse(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    urls: list[str] = []

    # RSS 2.0: <rss><channel><item><link>...</link></item></channel></rss>
    for item in root.iter("item"):
        link = item.findtext("link")
        if link:
            urls.append(link.strip())

    # Atom: <feed><entry><link href="..."/></entry></feed>
    for entry in root.iter(f"{_ATOM_NS}entry"):
        link_el = entry.find(f"{_ATOM_NS}link")
        if link_el is not None:
            href = link_el.get("href")
            if href:
                urls.append(href.strip())

    return urls
