"""httpx-based async fetch client with retries, rate limits, and caching.

The client wraps an :class:`httpx.AsyncClient` whose transport is layered
through :class:`hishel.httpx.AsyncCacheTransport` for on-disk HTTP caching.
A per-host semaphore caps concurrency, ``tenacity`` retries 5xx and 429
responses with exponential backoff, and a :class:`RobotsRegistry` checks
``robots.txt`` before any request.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from hishel.httpx import AsyncCacheTransport
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mfc.config import GlobalCrawlerPolicy
from mfc.fetch.cache import build_storage
from mfc.fetch.robots import RobotsRegistry


class RetryableHTTPError(Exception):
    """Raised on 5xx or 429 so tenacity can back off and retry."""


class RobotsDisallowed(Exception):
    """Raised when robots.txt forbids the requested URL."""


class FetchClient:
    """Cached, polite, retry-aware async fetcher."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        robots: RobotsRegistry,
        policy: GlobalCrawlerPolicy,
    ) -> None:
        self._client = client
        self._robots = robots
        self._policy = policy
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _semaphore(self, url: str) -> asyncio.Semaphore:
        host = urlsplit(url).netloc
        sem = self._semaphores.get(host)
        if sem is None:
            sem = asyncio.Semaphore(self._policy.max_concurrent_per_host)
            self._semaphores[host] = sem
        return sem

    async def get(self, url: str) -> httpx.Response:
        if self._policy.respect_robots_txt and not await self._robots.allowed(url):
            raise RobotsDisallowed(url)

        async with self._semaphore(url):
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._policy.retry_attempts + 1),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                retry=retry_if_exception_type(
                    (RetryableHTTPError, httpx.TransportError, httpx.TimeoutException)
                ),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.get(url)
                    if response.status_code == 429 or response.status_code >= 500:
                        logger.warning(
                            "retryable status; backing off",
                            url=url,
                            status=response.status_code,
                        )
                        raise RetryableHTTPError(f"{response.status_code} for {url}")
                    response.raise_for_status()
                    return response

        raise RuntimeError("unreachable: AsyncRetrying exited without returning")


@asynccontextmanager
async def open_fetch_client(policy: GlobalCrawlerPolicy) -> AsyncIterator[FetchClient]:
    """Build a :class:`FetchClient` and the underlying transport, then close them."""
    storage = build_storage()
    transport = AsyncCacheTransport(
        next_transport=httpx.AsyncHTTPTransport(http2=True),
        storage=storage,
    )
    headers = {"User-Agent": policy.user_agent}
    timeout = httpx.Timeout(policy.timeout_seconds)

    async with httpx.AsyncClient(
        transport=transport,
        headers=headers,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        robots = RobotsRegistry(client, user_agent=policy.user_agent)
        yield FetchClient(client, robots, policy)
