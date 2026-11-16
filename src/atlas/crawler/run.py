"""Run one crawl in its own process (Scrapy's event loop can start only once per process).

    python -m atlas.crawler.run <source> [--region R] [--max-pages N] [--delay S] [--fresh] [--spec-file F] [--allow-private]

The spec is the source's entry in config/sources.yaml (`type: crawl`), or a JSON file for tests.
Outputs: raw files + manifest (data/raw/web/<source>), frontier and report (data/crawl/<source>), documents table.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from scrapy.crawler import CrawlerProcess

from ..core import CRAWL, USER_AGENT, config, log
from . import docs as docs_mod
from . import report as report_mod
from .frontier import Frontier
from .spider import AtlasSpider


def settings(spec: dict, jobdir: str, frontier: str, delay: float, allow_private: bool) -> dict:
    budget = spec.get("budget", {})
    return {
        "BOT_NAME": "atlas-crawler",
        "USER_AGENT": USER_AGENT,
        "ROBOTSTXT_OBEY": True,
        "ROBOTSTXT_USER_AGENT": "accessibility-map",
        "COOKIES_ENABLED": False,
        "TELNETCONSOLE_ENABLED": False,
        "CONCURRENT_REQUESTS": spec.get("parallel_hosts", 8),
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": delay,
        "RANDOMIZE_DOWNLOAD_DELAY": delay >= 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": delay,
        "AUTOTHROTTLE_MAX_DELAY": 30,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [408, 429, 500, 502, 503, 504, 522, 524],
        "DOWNLOAD_TIMEOUT": 60,
        "DOWNLOAD_MAXSIZE": 50 * 1024 * 1024,
        "REDIRECT_MAX_TIMES": 5,
        "DEPTH_LIMIT": 0,
        "CLOSESPIDER_PAGECOUNT": (
            budget.get("auto_max", 500) if budget.get("pages") == "auto" else budget.get("pages", 300)
        )
        + budget.get("images", 80)
        + 100,  # hard safety cap
        "JOBDIR": jobdir,
        "LOG_LEVEL": "INFO",
        "ATLAS_FRONTIER": frontier,
        "ATLAS_ALLOW_PRIVATE": allow_private,
        "DOWNLOADER_MIDDLEWARES": {
            "atlas.crawler.middlewares.PrivateAddressMiddleware": 50,
            "atlas.crawler.middlewares.ConditionalGetMiddleware": 60,
            "atlas.crawler.middlewares.RetryAfterMiddleware": 560,  # above RetryMiddleware (550): sees 429/503 first
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="atlas.crawler.run")
    ap.add_argument("source")
    ap.add_argument("--region")
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument(
        "--fresh", action="store_true", help="forget the queue (not the frontier) and crawl again"
    )
    ap.add_argument("--spec-file")
    ap.add_argument(
        "--docs-only",
        action="store_true",
        help="do not crawl: rebuild the documents table from what is saved",
    )
    ap.add_argument("--allow-private", action="store_true", help="tests only: allow localhost")
    a = ap.parse_args(argv)

    spec = json.loads(Path(a.spec_file).read_text()) if a.spec_file else config("sources")[a.source]
    region = a.region or spec["regions"][0]
    if a.max_pages:
        spec.setdefault("budget", {})["pages"] = a.max_pages  # a fixed number overrides "auto"
    base = CRAWL / a.source
    jobdir = base / "jobdir"
    if a.fresh and jobdir.exists():
        shutil.rmtree(jobdir)
    crawl_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    frontier_path = base / "frontier.sqlite"
    logging.getLogger("scrapy").setLevel(logging.INFO)
    if a.docs_only:
        frontier = Frontier(base / "frontier.sqlite")
        df = docs_mod.build(a.source, region, spec, frontier)
        log.info("[%s] %s: rebuilt %d documents from the saved crawl", region, a.source, len(df))
        frontier.close()
        return 0
    process = CrawlerProcess(settings(spec, str(jobdir), str(frontier_path), a.delay, a.allow_private))
    crawler = process.create_crawler(AtlasSpider)
    process.crawl(
        crawler,
        source=a.source,
        spec=spec,
        frontier_path=str(frontier_path),
        crawl_id=crawl_id,
        recrawl=a.fresh,
    )
    process.start()

    spider = crawler.spider
    frontier = Frontier(frontier_path)
    rep = report_mod.build(frontier, getattr(spider, "close_reason", ""), spider.stopped_reason)
    rep.update(source=a.source, region=region, crawl_id=crawl_id)
    report_mod.write(base / "report.json", rep)
    df = docs_mod.build(a.source, region, spec, frontier)
    log.info("[%s] %s: %d urls, %d fetched, %d documents, ended: %s", region, a.source, rep["total_urls"],
             rep["by_state"].get("fetched", 0), len(df), rep["ended"])  # fmt: skip
    frontier.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
