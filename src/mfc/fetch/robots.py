"""robots.txt parsing and enforcement per host.

Async-loads ``/robots.txt`` once per host, caches the parsed
``RobotFileParser``, and exposes ``allowed(url)`` for callers. A host whose
``robots.txt`` returns a 4xx is treated as fully allowed (per RFC 9309). A
network failure or 5xx is treated as disallowed, conservatively.
"""

from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from loguru import logger


def _allow_all() -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse([])
    return parser


def _disallow_all() -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Disallow: /"])
    return parser


class RobotsRegistry:
    def __init__(self, client: httpx.AsyncClient, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    async def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host_key = f"{parts.scheme}://{parts.netloc}"
        parser = self._parsers.get(host_key)
        if parser is None:
            parser = await self._load(host_key)
            self._parsers[host_key] = parser
        return parser.can_fetch(self._user_agent, url)

    async def _load(self, host_key: str) -> RobotFileParser:
        try:
            response = await self._client.get(f"{host_key}/robots.txt")
        except httpx.HTTPError as err:
            logger.warning(
                "robots.txt fetch failed; treating host as disallowed",
                host=host_key,
                error=str(err),
            )
            return _disallow_all()

        if 400 <= response.status_code < 500:
            return _allow_all()
        if response.status_code >= 500:
            logger.warning(
                "robots.txt 5xx; treating host as disallowed",
                host=host_key,
                status=response.status_code,
            )
            return _disallow_all()

        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser
