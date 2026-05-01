"""Probe ClaimReview JSON-LD coverage on a handful of URLs per IFCN source.

For each source listed on the command line, samples up to N URLs from its
sitemap (no prefix filter) that look like article paths, fetches them, and
runs the JSON-LD extractor. Prints a per-source hit count and the URLs
that produced a hit.

Run:

    uv run python scripts/measure_claimreview_coverage.py \\
        newschecker_ml factcrescendo_en_malayalam_tag newsmeter_ml indiatoday_ml_afwa
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

from mfc.config import SourceConfig, SourcesFile
from mfc.discovery.sitemap import fetch_sitemap_urls
from mfc.extract.claimreview import extract_claimreview
from mfc.fetch.client import FetchClient, RobotsDisallowed, open_fetch_client

CONFIG_PATH = Path("configs/malayalam_factcheck_sources.json")
PER_SOURCE_SAMPLE = 10


def _looks_like_article(url: str) -> bool:
    path = urlsplit(url).path.rstrip("/")
    if not path:
        return False
    if path.endswith((".xml", ".jpg", ".png", ".webp", ".pdf")):
        return False
    return path.count("/") >= 2


async def _measure_source(client: FetchClient, src: SourceConfig) -> None:
    source_id = src.id
    assert src.discovery.sitemap is not None
    prefix = str(src.malayalam_section) if src.malayalam_section is not None else None
    candidates = await fetch_sitemap_urls(
        client, str(src.discovery.sitemap), url_prefix=prefix, max_urls=400
    )
    article_urls = [u for u in candidates if _looks_like_article(u)][:PER_SOURCE_SAMPLE]
    if not article_urls:
        print(f"{source_id}: 0 article-shaped URLs sampled from sitemap")
        return

    hits: list[str] = []
    for url in article_urls:
        try:
            response = await client.get(url)
        except RobotsDisallowed:
            continue
        except Exception as err:
            print(f"  fetch error {url}: {err}")
            continue
        result = extract_claimreview(response.text, url, body_selector=None, title_selector=None)
        if result is not None:
            hits.append(url)

    print(f"{source_id}: {len(hits)}/{len(article_urls)} ClaimReview JSON-LD hits")
    for url in hits:
        print(f"  hit: {url}")


async def main(source_ids: list[str]) -> None:
    config = SourcesFile.load(CONFIG_PATH)
    async with open_fetch_client(config.global_crawler_policy) as client:
        for sid in source_ids:
            try:
                src = config.source(sid)
            except KeyError:
                print(f"{sid}: not in config", file=sys.stderr)
                continue
            if src.discovery.sitemap is None:
                print(f"{sid}: no sitemap configured")
                continue
            try:
                await _measure_source(client, src)
            except Exception as err:
                print(f"{sid}: sitemap error: {err}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
