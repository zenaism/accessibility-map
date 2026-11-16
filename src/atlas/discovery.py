"""Automatic discovery of structured sources (route A in docs/national_data_plan.md): open-data catalogs searched for
a region. Candidates go into the candidate table and are rated by the trust engine; nobody picks them by hand.

    python -m atlas.cli discover <region>

Catalogs: ArcGIS Online (services and datasets whose extent overlaps the region's boundary box) and the Data.gov catalog
(CKAN). Both are free and need no key. Socrata portals are added per domain when one is known.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from . import candidates
from .core import config, fetch
from .regions import describe

TERMS = ["sidewalk", "curb ramp", "ADA", "crosswalk", "pedestrian signal", "accessibility", "wheelchair",
         "bus stop", "paratransit", "accessible parking", "311", "trail", "restroom"]  # fmt: skip
ARCGIS = "https://www.arcgis.com/sharing/rest/search"
CKAN = "https://catalog.data.gov/api/3/action/package_search"
SERVICE_TYPES = {"Feature Service", "Map Service", "CSV", "GeoJSON", "Shapefile", "Table", "KML"}
OFFICIAL = re.compile(
    r"\b(city|county|state|district|department|dept|transportation|dot|gis|government|metro|transit|planning|authority|bureau|office|engineer|commission|council|regional|mvrpc|rpc|mpo)\b|opendata|imap|engineer|mvrpc|[a-z]gis(?:$|[_.\-@])|dcgis|\bgov\b",
    re.I,
)
TOPIC = re.compile(
    r"sidewalk|curb|ramp|\bada\b|crosswalk|crossing|pedestrian|accessib|wheelchair|disab|bus stop|transit|paratransit|"
    r"signal|trail|restroom|toilet|parking|311|elevator|walk|path|bike|street ?light|sensory|barrier",
    re.I,
)
NOISE = re.compile(r"\b(test|sandbox|template|training|copy|demo|webmap|story ?map)\b", re.I)


def _year(ms) -> int | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, UTC).year
    except (TypeError, ValueError, OSError):
        return None


def kind_of(owner: str, title: str) -> str:
    """Who published it: an official inventory, an open dataset from an agency, or unknown."""
    if OFFICIAL.search(owner or ""):
        return (
            "official_inventory"
            if re.search(r"inventory|sidewalk|curb|ramp|crosswalk|ada|signal", title, re.I)
            else "open_dataset"
        )
    return "unknown"


def extent_fits(extent, bbox: list[float]) -> bool:
    """True when an item's extent is about this region: it overlaps the boundary box and is not vastly larger than it
    (a national or statewide layer that merely covers the city says nothing specific about it)."""
    try:
        (x0, y0), (x1, y1) = extent
    except (TypeError, ValueError):
        return False
    bx0, by0, bx1, by1 = bbox
    if x1 < bx0 or x0 > bx1 or y1 < by0 or y0 > by1:
        return False
    return (x1 - x0) * (y1 - y0) <= 60 * max((bx1 - bx0) * (by1 - by0), 1e-6)


def arcgis_items(bbox: list[float], term: str, num: int = 100) -> list[dict]:
    """Items whose extent overlaps the box. Many popular items have a world-wide extent and fill the top of any search, so
    ask for the maximum and filter here."""
    raw = json.loads(
        fetch(ARCGIS, params={"q": term, "bbox": ",".join(map(str, bbox)), "num": num, "f": "json"})
    )
    out = []
    for r in raw.get("results", []):
        text = f"{r.get('title', '')} {r.get('snippet') or ''} {' '.join(r.get('tags') or [])}"
        if r.get("type") not in SERVICE_TYPES or NOISE.search(r.get("title", "")) or not TOPIC.search(text):
            continue
        if not extent_fits(r.get("extent"), bbox):
            continue
        out.append(
            {
                "url": r.get("url") or f"https://www.arcgis.com/home/item.html?id={r['id']}",
                "title": r["title"],
                "publisher": r.get("owner", ""),
                "licence": re.sub(r"<[^>]+>", " ", r.get("licenseInfo") or "").strip()[:120],
                "data_year": _year(r.get("modified")),
                "kind": kind_of(r.get("owner", ""), r["title"]),
            }
        )
    return out


def ckan_items(place: str, term: str, rows: int = 10) -> list[dict]:
    raw = json.loads(fetch(CKAN, params={"q": f"{term} {place}", "rows": rows}))
    out = []
    for p in raw.get("result", {}).get("results", []):
        org = (p.get("organization") or {}).get("title", "")
        url = (
            next((r["url"] for r in p.get("resources", []) if r.get("url")), None)
            or f"https://catalog.data.gov/dataset/{p['name']}"
        )
        year = int((p.get("metadata_modified") or "0000")[:4]) or None
        out.append({"url": url, "title": p["title"], "publisher": org, "licence": (p.get("license_title") or "")[:120],
                    "data_year": year, "kind": kind_of(org, p["title"])})  # fmt: skip
    return out


def discover(region: str, terms: list[str] | None = None, limit_per_term: int = 8) -> list[dict]:
    """Find candidate sources for a region and add them (rated) to the candidate table. Returns the new rows."""
    cfg = config("regions")[region]
    bbox = describe(cfg["osm_relation"])["bbox"]
    place = cfg["name"].split(",")[0]
    df = candidates.load()
    before = set(df["candidate_id"]) if len(df) else set()
    for term in terms or TERMS:
        found = []
        try:
            found += arcgis_items(bbox, term)
        except Exception:
            pass  # one catalog being down must not stop the others
        try:
            found += ckan_items(place, term, 5)
        except Exception:
            pass
        for f in found:
            df = candidates.add(df, url=f["url"], title=f["title"], publisher=f["publisher"], region=region, route="A",
                                authority_kind=f["kind"], licence=f["licence"], data_year=f["data_year"])  # fmt: skip
    df = candidates.rate(df)
    candidates.save(df)
    return df[~df["candidate_id"].isin(before)].to_dict("records")
