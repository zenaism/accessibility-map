"""Crawl the own websites of places already on the map, then read them into facts tied to those places.

    python scripts/place_crawl.py --region oxford --categories restaurant,cafe --limit 40 [--delay 2]

Steps: places with a website from the Overture data -> crawl spec (config/crawl/places_<region>_<name>.json) -> polite crawl
-> documents (each page knows its place) -> rule-based facts. Uses only places' own sites, robots.txt is obeyed.
"""

import argparse
import json
import subprocess
import sys

from atlas.core import ROOT
from atlas.crawler import seeds

ap = argparse.ArgumentParser()
ap.add_argument("--region", required=True)
ap.add_argument(
    "--categories", default="restaurant,cafe,bar,coffee_shop,bakery,fast_food_restaurant,ice_cream_shop"
)
ap.add_argument("--limit", type=int, default=40)
ap.add_argument("--per-host", type=int, default=8)
ap.add_argument("--delay", type=float, default=2.0)
ap.add_argument("--name", default="food")
a = ap.parse_args()

found = seeds.places(a.region, set(a.categories.split(",")), a.limit)
spec = seeds.crawl_spec(a.region, found, a.per_host)
source = f"places_{a.region}_{a.name}"
f = ROOT / "config" / "crawl" / f"{source}.json"
f.write_text(json.dumps(spec, indent=1))
print(f"{len(found)} places with their own website; spec written to {f.relative_to(ROOT)}")
subprocess.run(
    [
        sys.executable,
        "-W",
        "ignore",
        "-m",
        "atlas.crawler.run",
        source,
        "--spec-file",
        str(f),
        "--region",
        a.region,
        "--delay",
        str(a.delay),
        "--fresh",
    ],
    check=True,
)
subprocess.run(
    [sys.executable, "-W", "ignore", "-m", "atlas.cli", "extract", source, "--region", a.region], check=True
)
