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
from scrapy import Selector, signals
from scrapy.exceptions import CloseSpider, IgnoreRequest

from ..connectors.web import _clean_html
from . import archive, relevance, urls
from .frontier import Frontier
from .render import Renderer, needs_render

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
        raw = budget.get("pages", 300)  # pages and documents; images have their own budget
        # "auto": start small, then grow with the site's own sitemap (about 1.3 x its URLs + 50), up to auto_max
        self.auto, self.auto_max, self.sitemap_total = raw == "auto", budget.get("auto_max", 500), 0
        self.max_pages = budget.get("auto_min", 80) if self.auto else raw
        self.max_images = budget.get("images", 80)
        self.pages_done = self.images_done = self.images_queued = 0
        self.family = {}  # (section, path depth) -> [relevant pages, pages]: which parts of a site hold what we want
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
        self.rendered = 0
        self.render_mode = spec.get("render", "auto")  # auto | always | never
        self.renderer = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        if spider.render_mode != "never":
            st = crawler.settings
            spider.renderer = Renderer(
                delay=st.getfloat("DOWNLOAD_DELAY", 2.0), allow_private=st.getbool("ATLAS_ALLOW_PRIVATE")
            )
        crawler.signals.connect(spider._close_browser, signal=signals.spider_closed)
        return spider

    async def _close_browser(self, spider=None, reason=None):
        if self.renderer:
            await self.renderer.close()

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
            meta={"atlas_depth": depth, "score": score, "via": via, "handle_httpstatus_all": True},
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
        if sm_type == "urlset" and self.auto:
            self.sitemap_total += len(sm_entries)
            self.max_pages = min(self.auto_max, max(self.max_pages, int(1.3 * self.sitemap_total) + 50))
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
    async def parse_page(self, response):
        url = response.request.url
        meta = response.meta
        depth = meta.get("atlas_depth", 0)
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
        if urls.kind(url) == "image":
            self.images_done += 1
        else:
            self.pages_done += 1
        if self.bytes_total > self.max_bytes:
            self.stop("byte budget reached")
        elif self.pages_done >= self.max_pages:
            self.stop("page budget reached")
        if self.stopped_reason:
            raise CloseSpider(self.stopped_reason)  # really stop: the queue is not drained
        if not ctype.startswith(HTML):
            self.recent.append(
                1.0 if relevance.score_url(url) > 0.2 else 0.0
            )  # a document: judged by its address
            return
        title, text, links = _clean_html(response.body, response.url)
        sel = response  # where to look for links: the plain page, or the rendered page below
        if self.renderer and needs_render(text, response.body, self.render_mode):
            rr = await self.renderer.render(
                response.url
            )  # thin page: load it in a real browser, open what is hidden
            if rr:
                rrec = archive.save(
                    self.source, url, rr["final_url"], rr["status"], "text/html", {}, rr["html"],
                    rendered=True, screenshot=rr["screenshot"],
                )  # fmt: skip
                title, text, links = _clean_html(rr["html"], rr["final_url"])
                sel = Selector(text=rr["html"].decode("utf-8", "ignore"))
                self.frontier.update(
                    url,
                    rendered=1,
                    content_sha=rrec["sha256"],
                    bytes=len(rr["html"]),
                    final_url=rr["final_url"],
                )
                self.rendered += 1
        page_score = max(relevance.score_text(text), meta.get("score", 0.0) * 0.5)
        self.frontier.update(url, score=round(page_score, 3))
        self.recent.append(page_score)
        self.learn(url, page_score >= 0.1)
        self.check_adaptive_stop()
        if self.stopped_reason:
            raise CloseSpider(self.stopped_reason)
        if depth >= self.max_depth:
            return
        anchors = {}
        for a in sel.css("a[href]"):
            anchors.setdefault(a.attrib["href"], " ".join(a.css("::text").getall()).strip())
        for href in dict.fromkeys(links):
            anchor = anchors.get(href, "")
            # pagination and directory links stay at the same depth: page 5 of a listing is not "five clicks deep"
            for req in self.consider(
                href, anchor, page_score, depth if relevance.is_listing(href, anchor) else depth + 1, url
            ):
                yield req
        for css in (
            "iframe::attr(src)",
            "link[rel=next]::attr(href)",
            "embed::attr(src)",
            "object::attr(data)",
        ):
            for href in sel.css(css).getall():
                for req in self.consider(href, "", page_score, depth + 1, url, via="embedded"):
                    yield req
        if self.discover["feeds"]:
            for link in sel.css("link[rel=alternate]"):
                if link.attrib.get("type", "") in FEED_TYPES and link.attrib.get("href"):
                    for req in self.consider(
                        link.attrib["href"], "feed", page_score, depth + 1, url, via="feed"
                    ):
                        yield req

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
        if k == "image" and self.images_queued >= self.max_images:
            return skip("image budget")
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
        score = self.adjust(u, score, anchor, via, k)
        explore = hash(u) % 100 < self.explore * 100
        if score < 0.05 and not explore and via == "link" and depth > 1:
            return skip("low relevance")
        self.section_count[row["section"]] += 1
        self.images_queued += k == "image"
        self.frontier.add(u, score=score, **row)
        yield self._req(u, depth, score, relevance.priority(score), via=via)

    def adjust(self, url: str, score: float, anchor: str, via: str, k: str) -> float:
        """Signals beyond the words: the site's own sitemap, pagination, and what similar pages turned out to hold."""
        if k == "image":
            return 0.3  # pictures interleave with pages (they have their own budget), behind sitemap pages
        if via == "sitemap":
            score = max(score, 0.6)  # the site itself lists this page: worth fetching, ahead of guessed links
        if via == "embedded" or relevance.is_listing(url, anchor):
            score = max(score, 0.4)  # listing and pagination pages lead to the entries
        seen = self.family.get(urls.family_key(url))
        if seen and seen[1] >= 2:
            score = min(1.0, score + 0.4 * seen[0] / seen[1])  # sibling pages were relevant: so is this one
        return round(score, 3)

    def learn(self, url: str, relevant: bool):
        f = self.family.setdefault(urls.family_key(url), [0, 0])
        f[0] += int(relevant)
        f[1] += 1

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
