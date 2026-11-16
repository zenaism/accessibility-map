"""Recall test (docs/crawler_plan.md section 10): give the crawler only a site's homepage and measure how many
of the pages we picked by hand for that source it finds by itself.

    python scripts/crawl_recall.py web_trails_oxford --pages 60 --delay 2

Writes data/crawl/recall_<source>/recall.json. Real websites: keep --delay at 2 or more and the page budget small.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from atlas.core import CRAWL, config
from atlas.crawler import urls
from atlas.crawler.frontier import Frontier

ap = argparse.ArgumentParser()
ap.add_argument("source")
ap.add_argument("--pages", type=int, default=60)
ap.add_argument("--delay", type=float, default=2.0)
ap.add_argument("--depth", type=int, default=3)
a = ap.parse_args()

hand_spec = config("sources")[a.source]
hand = {u for u in (urls.normalize(x) for x in hand_spec["urls"]) if u}
hosts = {urls.host_key(u) for u in hand}
seeds = sorted({"{0.scheme}://{0.netloc}/".format(urlsplit(u)) for u in hand})
name = f"recall_{a.source}"
spec = {
    "regions": hand_spec["regions"],
    "author_type": hand_spec.get("author_type", "official"),
    "seeds": seeds,
    "scope": {"hosts": sorted(hosts), "depth": a.depth},
    "budget": {"pages": "auto", "auto_max": a.pages, "images": 30, "megabytes": 200, "per_pattern": 25},
    "assets": "all",
    "explore_share": 0.1,
}
spec_file = CRAWL / name / "spec.json"
spec_file.parent.mkdir(parents=True, exist_ok=True)
spec_file.write_text(json.dumps(spec, indent=2))
subprocess.run([sys.executable, "-m", "atlas.crawler.run", name, "--spec-file", str(spec_file), "--delay", str(a.delay), "--fresh"], check=True)

f = Frontier(CRAWL / name / "frontier.sqlite")
rows = {r["url"]: r for r in f.rows()}
f.close()
found = {u for u in hand if u in rows and rows[u]["state"] in ("fetched", "unchanged")}
misses = {u: (rows[u]["state"], rows[u]["reason"]) if u in rows else ("never seen", "") for u in hand - found}
out = {
    "source": a.source,
    "hand_picked": len(hand),
    "found": len(found),
    "recall": round(len(found) / len(hand), 3),
    "pages_fetched": sum(1 for r in rows.values() if r["state"] == "fetched"),
    "misses": misses,
}
(CRAWL / name / "recall.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "misses"}, indent=2))
for u, why in misses.items():
    print("  missed:", u, why)
