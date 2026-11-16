"""Politeness and safety for every request the crawler makes."""

from __future__ import annotations

import asyncio
import email.utils
import ipaddress
import socket
import time
from urllib.parse import urlsplit

from scrapy.exceptions import IgnoreRequest

from .frontier import Frontier


class PrivateAddressMiddleware:
    """Refuse addresses on our own network (a malicious page could point the crawler at them). Off only in tests."""

    def __init__(self, allow: bool):
        self.allow, self.cache = allow, {}

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getbool("ATLAS_ALLOW_PRIVATE"))

    def _private(self, host: str) -> bool:
        if host not in self.cache:
            try:
                infos = socket.getaddrinfo(host, None)
                self.cache[host] = any(
                    (ip := ipaddress.ip_address(i[4][0])).is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    for i in infos
                )
            except (OSError, ValueError):
                self.cache[host] = False  # unresolvable: the download will fail on its own
        return self.cache[host]

    def process_request(self, request, spider=None):
        if not self.allow and self._private(urlsplit(request.url).hostname or ""):
            raise IgnoreRequest("private or local address")


class ConditionalGetMiddleware:
    """On a re-crawl send If-None-Match / If-Modified-Since from the frontier, so unchanged pages cost almost nothing."""

    def __init__(self, frontier_path: str | None):
        self.path = frontier_path
        self.frontier = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get("ATLAS_FRONTIER"))

    def process_request(self, request, spider=None):
        if not self.path or request.meta.get("robots_probe"):
            return
        if self.frontier is None:
            from pathlib import Path

            self.frontier = Frontier(Path(self.path))
        row = self.frontier.get(request.url)
        if row and row.get("content_sha"):  # we have fetched this page before
            if row.get("etag"):
                request.headers["If-None-Match"] = row["etag"]
            if row.get("last_modified"):
                request.headers["If-Modified-Since"] = row["last_modified"]
            request.meta["conditional"] = True


class RetryAfterMiddleware:
    """Honour Retry-After on 429 and 503: pause every request to that host until the time it names. Sits just
    above the retry middleware so it sees the response first; the retry then waits in process_request."""

    MAX_WAIT = 120.0

    def __init__(self, max_wait: float):
        self.max_wait, self.until = max_wait, {}

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getfloat("ATLAS_MAX_RETRY_AFTER", cls.MAX_WAIT))

    @staticmethod
    def parse(value: str) -> float | None:
        if not value:
            return None
        if value.strip().isdigit():
            return float(value)
        try:
            return max(0.0, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError):
            return None

    async def process_request(self, request, spider=None):
        host = urlsplit(request.url).hostname
        wait = self.until.get(host, 0) - time.time()
        if wait > 0:
            await asyncio.sleep(wait)

    def process_response(self, request, response, spider=None):
        if response.status in (429, 503):
            wait = self.parse(response.headers.get("Retry-After", b"").decode("latin1"))
            if wait is not None:
                host = urlsplit(request.url).hostname
                self.until[host] = time.time() + min(wait, self.max_wait)
        return response
