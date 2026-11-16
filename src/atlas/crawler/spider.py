"""The crawl itself: seeds -> sitemaps and feeds -> best-first link following, inside scope, politeness and budgets.

Every URL gets a frontier row and a final state, so the completeness report can show exactly what happened.
"""

from __future__ import annotations

import gzip
import re
from collections import Counter, deque
from pathlib import Path
from urllib.parse import urlsplit

import scrapy
from lxml import etree
from scrapy.exceptions import IgnoreRequest

from ..connectors.web import _clean_html
from . import archive, relevance, urls
from .frontier import Frontier

HTML = ("text/html", "application/xhtml")
SITEMAP_PATHS = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "text/calendar")


def read_sitemap(body: bytes) -> tuple[str, list[dict]]:
    """("urlset" | "sitemapindex", [{loc, lastmod}]) from sitemap XML, whatever its namespace."""
    root = etree.fromstring(
        body, parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
    )
    kind = etree.QName(root).localname
    out = []
    for el in root:
        d = {etree.QName(c).localname: (c.text or "").strip() for c in el if isinstance(c.tag, str)}
        if d.get("loc"):
            out.append(d)
    return kind, out


class AtlasSpider(scrapy.Spider):
    name = "atlas"

    def __init__(
        self, source: str, spec: dict, frontier_path: str, crawl_id: str = "", recrawl: bool = False, **kw
    ):
        super().__init__(**kw)
        self.source, self.spec, self.crawl_id, self.recrawl = source, spec, crawl_id, recrawl
        self.frontier = Frontier(Path(frontier_path))
        scope = spec.get("scope", {})
        seeds = [urls.normalize(s) for s in spec["seeds"]]
        self.seeds = [s for s in seeds if s]
        self.hosts = {urls.host_key(s) for s in self.seeds} | {
            urls.host_key(h) for h in scope.get("hosts", [])
        }
        self.max_depth = scope.get("depth", 4)
        budget = spec.get("budget", {})
        self.max_bytes = budget.get("megabytes", 500) * 1_000_000
        self.per_section = budget.get("per_section", 10**9)
        self.per_pattern = budget.get("per_pattern", 40)
        self.discover = {"sitemaps": True, "feeds": True, "probe_paths": True} | spec.get("discover", {})
        self.assets = spec.get("assets", "all")  # all | maps | none
        self.explore = spec.get("explore_share", 0.1)
        self.adaptive = spec.get("adaptive_stop", {"window": 40, "min_pages": 80, "threshold": 0.05})
        self.bytes_total = 0
        self.recent = deque(maxlen=self.adaptive["window"])
        self.section_count = Counter()
        self.stopped_reason = None
        self.fetched = 0

    # ---- start: seeds, robots.txt (for Sitemap lines), probes -------------------------------------------------------
    async def start(self):
        if (
            self.recrawl
        ):  # a new crawl of a known site: ask again for every page, conditionally (304 = unchanged)
            for row in sorted(self.frontier.rows(), key=lambda r: -(r["score"] or 0)):
                if row["state"] in ("fetched", "unchanged") and row["via"] not in ("robots", "sitemap-file"):
                    self.frontier.update(row["url"], state="queued", reason="recrawl")
                    yield self._req(
                        row["url"],
                        row["depth"] or 0,
                        row["score"] or 0.0,
                        relevance.priority(row["score"] or 0.0),
                    )
        hosts_done = set()
        for seed in self.seeds:
            if self.frontier.add(
                seed, host=urls.host_key(seed), depth=0, via="seed", score=1.0, section=urls.section(seed)
            ):
                yield self._req(seed, 0, 1.0, 100)
            origin = "{0.scheme}://{0.netloc}".format(urlsplit(seed))
            if origin in hosts_done:
                continue
            hosts_done.add(origin)
            if self.discover["sitemaps"]:
                yield scrapy.Request(
                    origin + "/robots.txt", callback=self.parse_robots, errback=self.on_probe_error,
                    meta={"robots_probe": True, "dont_obey_robotstxt": True, "origin": origin, "handle_httpstatus_all": True}, dont_filter=True, priority=1000,
                )  # fmt: skip
            if self.discover["probe_paths"]:
                for path in relevance.PROBE_PATHS:
                    u = urls.normalize(origin + path)
                    if u and self.frontier.add(
                        u, host=urls.host_key(u), depth=1, via="probe", score=0.5, section=urls.section(u)
                    ):
                        yield self._req(u, 1, 0.5, 40)

    def _req(
        self, url: str, depth: int, score: float, priority: int, callback=None, via: str = "link"
    ) -> scrapy.Request:
        return scrapy.Request(
            url, callback=callback or self.parse_page, errback=self.on_error, priority=priority,
            meta={"depth": depth, "score": score, "via": via, "handle_httpstatus_all": True},
        )  # fmt: skip

    def parse_robots(self, response):
        origin = response.meta["origin"]
        self.frontier.add(
            origin + "/robots.txt",
            host=urls.host_key(origin),
            state="fetched",
            via="robots",
            status=response.status,
        )
        found = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", response.text) if response.status == 200 else []
        for sm in found or [origin + p for p in SITEMAP_PATHS]:
            u = urls.normalize(sm)
            if (
                u
                and urls.in_scope(u, self.hosts)
                and self.frontier.add(u, host=urls.host_key(u), depth=0, via="sitemap-file")
            ):
                yield scrapy.Request(
                    u, callback=self.parse_sitemap, errback=self.on_probe_error, priority=900,
                    meta={"robots_probe": True, "sitemap": True, "handle_httpstatus_all": True}, dont_filter=True,
                )  # fmt: skip

    def on_probe_error(self, failure):
        self.log_failure(failure, failure.request.url)

    # ---- sitemaps ---------------------------------------------------------------------------------------------------
    def parse_sitemap(self, response):
        url = response.url
        if response.status != 200:
            self.frontier.update(
                url, state="skipped", reason=f"no sitemap (HTTP {response.status})", status=response.status
            )
            return
        body = response.body
        if body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)
            except OSError:
                self.frontier.update(url, state="failed", reason="bad gzip sitemap")
                return
        self.frontier.update(url, state="fetched", status=200, via="sitemap-file")
        try:
            sm_type, sm_entries = read_sitemap(body)
        except Exception:  # not a sitemap (soft 404 page)
            self.frontier.update(url, state="skipped", reason="not a sitemap")
            return
        for entry in sm_entries:
            loc = urls.normalize(entry.get("loc", ""), url)
            if not loc:
                continue
            if sm_type == "sitemapindex":
                if urls.in_scope(loc, self.hosts) and self.frontier.add(
                    loc, host=urls.host_key(loc), depth=0, via="sitemap-file"
                ):
                    yield scrapy.Request(loc, callback=self.parse_sitemap, errback=self.on_probe_error, priority=900,
                                         meta={"robots_probe": True, "sitemap": True, "handle_httpstatus_all": True}, dont_filter=True)  # fmt: skip
            else:
                yield from self.consider(loc, "", 0.0, 1, url, via="sitemap", lastmod=entry.get("lastmod"))

    # ---- pages ------------------------------------------------------------------------------------------------------
    def parse_page(self, response):
        url = response.request.url
        meta = response.meta
        depth = meta.get("depth", 0)
        status = response.status
        if status == 304:
            self.frontier.update(url, state="unchanged", status=304, last_fetched=self._now())
            return
        if status >= 400:
            self.frontier.update(
                url,
                state="failed",
                status=status,
                reason=f"HTTP {status}",
                attempts=meta.get("retry_times", 0),
            )
            return
        ctype = response.headers.get("Content-Type", b"").decode("latin1").split(";")[0].strip().lower()
        headers = {k.decode().lower(): v[0].decode("latin1") for k, v in response.headers.items()}
        rec = archive.save(self.source, url, response.url, status, ctype, headers, response.body)
        before = (self.frontier.get(url) or {}).get("content_sha")
        self.frontier.update(
            url, state="fetched", status=status, content_type=ctype, bytes=len(response.body), content_sha=rec["sha256"],
            final_url=response.url, etag=headers.get("etag"), last_modified=headers.get("last-modified"),
            last_fetched=rec["retrieved_at"], crawl_id=self.crawl_id, attempts=meta.get("retry_times", 0),
            change_count=(self.frontier.get(url) or {}).get("change_count", 0) + (1 if before and before != rec["sha256"] else 0),
        )  # fmt: skip
        self.fetched += 1
        self.bytes_total += len(response.body)
        if self.bytes_total > self.max_bytes:
            self.stop("byte budget reached")
            return
        if not ctype.startswith(HTML):
            self.recent.append(
                1.0 if relevance.score_url(url) > 0.2 else 0.0
            )  # a document: judged by its address
            return
        title, text, links = _clean_html(response.body, response.url)
        page_score = max(relevance.score_text(text), meta.get("score", 0.0) * 0.5)
        self.frontier.update(url, score=round(page_score, 3))
        self.recent.append(page_score)
        self.check_adaptive_stop()
        if depth >= self.max_depth:
            return
        anchors = {}
        for a in response.css("a[href]"):
            anchors.setdefault(a.attrib["href"], " ".join(a.css("::text").getall()).strip())
        for href in dict.fromkeys(links):
            yield from self.consider(href, anchors.get(href, ""), page_score, depth + 1, url)
        for sel in (
            "iframe::attr(src)",
            "link[rel=next]::attr(href)",
            "embed::attr(src)",
            "object::attr(data)",
        ):
            for href in response.css(sel).getall():
                yield from self.consider(href, "", page_score, depth + 1, url, via="embedded")
        if self.discover["feeds"]:
            for link in response.css("link[rel=alternate]"):
                if link.attrib.get("type", "") in FEED_TYPES and link.attrib.get("href"):
                    yield from self.consider(
                        link.attrib["href"], "feed", page_score, depth + 1, url, via="feed"
                    )

    # ---- deciding what to fetch -------------------------------------------------------------------------------------
    def consider(self, href, anchor, parent_score, depth, parent, via="link", lastmod=None):
        u = urls.normalize(href, parent)
        if not u or self.stopped_reason or self.frontier.known(u):
            return
        row = {"host": urls.host_key(u), "depth": depth, "via": via, "parent": parent, "section": urls.section(u), "lastmod": lastmod,
               "pattern": urls.pattern_key(u)}  # fmt: skip

        def skip(reason: str):
            self.frontier.add(u, state="skipped", reason=reason, **row)

        if not urls.in_scope(u, self.hosts):
            return skip("off-site")
        k = urls.kind(u)
        if k == "skip":
            return skip("file type not wanted")
        if k == "image" and self.assets == "none":
            return skip("images not wanted")
        if k == "image" and self.assets == "maps" and not relevance.score_url(u, anchor) > 0.2:
            return skip("image not map-like")
        if (reason := urls.trap_reason(u)) and via != "sitemap":
            return skip(f"trap guard: {reason}")
        if self.frontier.count_where("pattern", row["pattern"]) >= self.per_pattern:
            return skip("pattern budget")
        if self.section_count[row["section"]] >= self.per_section:
            return skip("section budget")
        score = relevance.score_url(u, anchor, parent_score)
        explore = hash(u) % 100 < self.explore * 100
        if score < 0.05 and not explore and via == "link" and depth > 1:
            return skip("low relevance")
        self.section_count[row["section"]] += 1
        self.frontier.add(u, score=score, **row)
        yield self._req(u, depth, score, relevance.priority(score), via=via)

    def check_adaptive_stop(self):
        a = self.adaptive
        if (
            self.fetched >= a["min_pages"]
            and len(self.recent) == a["window"]
            and max(self.recent) < a["threshold"]
        ):
            self.stop(f"adaptive stop: the last {a['window']} pages added nothing relevant")

    def stop(self, reason: str):
        if not self.stopped_reason:
            self.stopped_reason = reason
            self.logger.info("stopping: %s", reason)

    # ---- failures ---------------------------------------------------------------------------------------------------
    def on_error(self, failure):
        self.log_failure(failure, failure.request.url)

    def log_failure(self, failure, url: str):
        exc = failure.value
        if isinstance(exc, IgnoreRequest):
            msg = str(exc)
            robots = "robots" in msg.lower() or "forbidden by robots" in msg.lower()
            self.frontier.update(url, state="blocked", reason="robots.txt" if robots else msg[:80])
        else:
            self.frontier.update(url, state="failed", reason=type(exc).__name__)

    @staticmethod
    def _now() -> str:
        from ..core import now

        return now()

    def closed(self, reason):
        self.close_reason = self.stopped_reason or reason
