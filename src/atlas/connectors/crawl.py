"""`type: crawl` sources: run the crawler (docs/crawler_plan.md) for one source, in its own process."""

from __future__ import annotations

import subprocess
import sys

from ..core import log


def run(name: str, spec: dict, region: str) -> None:
    cmd = [sys.executable, "-m", "atlas.crawler.run", name, "--region", region]
    if spec.get("delay"):
        cmd += ["--delay", str(spec["delay"])]
    log.info("[%s] %s: crawling", region, name)
    subprocess.run(cmd, check=True)
