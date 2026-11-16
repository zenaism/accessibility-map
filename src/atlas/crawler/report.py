"""The coverage report: what the crawl fetched, skipped, blocked and missed, and why (completeness gates 1, 2 and 7)."""

from __future__ import annotations

import json
from pathlib import Path

from .frontier import Frontier


def build(frontier: Frontier, close_reason: str = "", stopped: str | None = None) -> dict:
    counts = frontier.counts()
    rows = frontier.rows()
    # pages skipped on purpose (other languages, off-site, unwanted types) are not "missed": leave them out of the coverage
    sitemap_rows = [r for r in rows if r["via"] == "sitemap" and r["state"] != "skipped"]
    sitemap_listed = sum(1 for r in rows if r["via"] == "sitemap")
    in_sm = len(sitemap_rows)
    got = sum(1 for r in sitemap_rows if r["state"] in ("fetched", "unchanged"))
    unfinished = counts.get("queued", 0)
    pages = [r for r in rows if r["state"] == "fetched" and (r["content_type"] or "").startswith("text/html")]
    report = {
        "total_urls": sum(counts.values()),
        "by_state": dict(counts),
        "skipped_reasons": dict(frontier.reasons("skipped")),
        "failed_reasons": dict(frontier.reasons("failed")),
        "blocked_reasons": dict(frontier.reasons("blocked")),
        "sitemap": {
            "urls": sitemap_listed,
            "wanted": in_sm,
            "fetched": got,
            "coverage": round(got / in_sm, 3) if in_sm else None,
        },
        "discovered_via": {
            v: sum(1 for r in rows if r["via"] == v) for v in sorted({r["via"] for r in rows if r["via"]})
        },
        "unfinished_queued": unfinished,
        "html_pages": len(pages),
        "rendered_in_browser": sum(1 for r in rows if r.get("rendered")),
        "bytes": sum(r["bytes"] or 0 for r in rows),
        "ended": stopped or close_reason,
        "complete": unfinished == 0 and not stopped,
        # Gate 1: every URL has a final state. 'queued' left over means the crawl stopped on a budget or was interrupted.
        "gate_status_audit": unfinished == 0,
        "gate_sitemap_coverage": (got / in_sm >= 0.95) if in_sm else None,
    }
    return report


def write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
