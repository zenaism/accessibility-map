"""Place-driven seeds (docs/crawler_plan.md 6.1): the websites of places already on the map become crawl seeds, and every
page the crawler finds on such a site is tied back to its place. No search engine and no hand-picked list.

    python scripts/place_crawl.py --region oxford --categories restaurant,cafe --limit 40
"""

from __future__ import annotations

from urllib.parse import urlsplit

import geopandas as gpd

from ..core import PROCESSED
from . import urls

# sites that are directories, social pages, ticket or delivery services, not the place's own website
AGGREGATORS = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "yelp.com", "tripadvisor.", "google.", "goo.gl", "seatgeek.com",
    "eventbrite.", "booking.com", "doordash.com", "ubereats.com", "grubhub.com", "opentable.com", "linktr.ee", "linkedin.com",
    "youtube.com", "tiktok.com", "yellowpages.com", "mapquest.com", "foursquare.com", "bing.com", "yahoo.com", "barberly.app",
    "squareup.com", "toasttab.com", "order.online", "clover.com", "menufy.com", "chownow.com", "allmenus.com",
)  # fmt: skip
FOOD = {
    "restaurant",
    "cafe",
    "bar",
    "fast_food_restaurant",
    "coffee_shop",
    "bakery",
    "ice_cream_shop",
    "eat_and_drink",
}


def own_site(url: str) -> bool:
    host = urls.host_key(url)
    return bool(host) and not any(a in host for a in AGGREGATORS)


def places(region: str, categories: set[str] | None = None, limit: int = 50) -> list[dict]:
    """Places of a region with their own website, best-confidence first, one per website host."""
    e = gpd.read_parquet(PROCESSED / region / "overture_places.entities.parquet")
    e = e[e.website.notna() & e.website.astype(str).str.startswith("http")]
    hosts = e.website.map(urls.host_key)
    e = e[
        hosts.map(hosts.value_counts()) < 3
    ]  # a website shared by three or more places is a chain: crawl locals, not corporate sites
    if categories:
        e = e[e.basic_category.isin(categories)]
    e = e[e.website.map(own_site)].sort_values("confidence", ascending=False)
    out, seen = [], set()
    for r in e.itertuples():
        host = urls.host_key(r.website)
        if host in seen:
            continue  # a chain with many locations shares one website: take it once
        seen.add(host)
        out.append(
            {
                "place_id": r.entity_id,
                "name": r.name,
                "category": r.basic_category,
                "website": r.website,
                "host": host,
            }
        )
        if len(out) >= limit:
            break
    return out


def crawl_spec(region: str, found: list[dict], per_host: int = 8, depth: int = 2) -> dict:
    seeds = []
    for p in found:
        u = urls.normalize(p["website"])
        parts = urlsplit(u)
        seeds.append(
            f"{parts.scheme}://{parts.netloc}{parts.path or '/'}"
        )  # the page given, without tracking parameters
    return {
        "regions": [region],
        "author_type": "business",
        "seeds": seeds,
        "scope": {"depth": depth},
        "budget": {
            "pages": per_host * len(found) + 20,
            "per_host": per_host,
            "images": 0,
            "megabytes": 400,
            "per_pattern": 10,
        },
        "assets": "none",
        "discover": {"sitemaps": True, "feeds": False, "probe_paths": True},
        "render": "auto",
        "explore_share": 0.0,
        "host_patience": 5,  # give up on a site after five pages with no accessibility words (most small sites have none)
        "seed_places": {p["host"]: {k: p[k] for k in ("place_id", "name", "category")} for p in found},
    }
