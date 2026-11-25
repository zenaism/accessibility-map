"""Region resolver: find a place's OSM boundary, check it, and pin it in config/regions.yaml.

    python -m atlas.cli region search "Dayton, Ohio"
    python -m atlas.cli region add dayton "Dayton, Ohio" --relation 182954 --buffer-km 20

A region is always a pinned OpenStreetMap relation id, never matched by name (the predecessor project matched
"Manhattan" to Manhattan, Kansas). `search` lists the candidates with their area so a wrong match is obvious;
`add` refuses a boundary whose area is implausible for a city and appends the entry (comments are kept).
"""

from __future__ import annotations

import csv
import json
import math
import re

import geopandas as gpd
from shapely.geometry import shape

from .core import ROOT, WGS84, config, fetch

NOMINATIM = "https://nominatim.openstreetmap.org"
EQUAL_AREA = "EPSG:5070"  # CONUS Albers: areas in square metres
MIN_KM2, MAX_KM2 = 5, 20000  # a city boundary outside this range is almost certainly the wrong object
FILE = ROOT / "config" / "regions.yaml"


def search(query: str, limit: int = 8) -> list[dict]:
    """Relation candidates for a place name (US), best first."""
    raw = json.loads(
        fetch(
            f"{NOMINATIM}/search",
            params={
                "q": query,
                "format": "jsonv2",
                "countrycodes": "us",
                "limit": limit,
                "addressdetails": 1,
                "extratags": 1,
            },
        )
    )
    out = []
    for c in raw:
        if c.get("osm_type") != "relation":
            continue
        tags = c.get("extratags") or {}
        out.append({
            "osm_relation": int(c["osm_id"]),
            "name": c["display_name"],
            "category": f"{c.get('category')}/{c.get('type')}",
            "admin_level": tags.get("admin_level"),
            "wikidata": tags.get("wikidata"),
        })  # fmt: skip
    return out


def describe(relation: int) -> dict:
    """Area (km2), bounding box and centre of a relation's boundary, from its real polygon."""
    gj = json.loads(
        fetch(
            f"{NOMINATIM}/lookup",
            params={"osm_ids": f"R{relation}", "format": "geojson", "polygon_geojson": 1},
        )
    )
    if not gj.get("features"):
        raise ValueError(f"OSM relation {relation} not found")
    g = shape(gj["features"][0]["geometry"])
    km2 = gpd.GeoSeries([g], crs=WGS84).to_crs(EQUAL_AREA).area.iloc[0] / 1e6
    c = g.representative_point()
    return {
        "area_km2": round(km2, 1),
        "bbox": [round(x, 4) for x in g.bounds],
        "lon": round(c.x, 4),
        "lat": round(c.y, 4),
    }


def utm_epsg(lon: float, lat: float) -> int:
    """UTM zone for a point (north: 326xx, south: 327xx), so distances in a region use its own zone."""
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def add(key: str, name: str, relation: int, buffer_km: float = 15, note: str = "") -> dict:
    """Append a region to config/regions.yaml after checking the boundary. Returns the description."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise ValueError("key must be lowercase letters, digits and underscores")
    cfg = config("regions")
    if key in cfg:
        raise ValueError(f"region {key!r} already exists")
    if any(v.get("osm_relation") == relation for v in cfg.values()):
        raise ValueError(f"relation {relation} is already used by another region")
    info = describe(relation)
    if not MIN_KM2 <= info["area_km2"] <= MAX_KM2:
        raise ValueError(f"boundary area {info['area_km2']} km2 is implausible for a city: wrong relation?")
    comment = f"   # {note}" if note else ""
    block = (
        f"{key}:\n  name: {name}\n  osm_relation: {relation}{comment}\n  buffer_km: {buffer_km}\n"
        f"  # area {info['area_km2']} km2; UTM zone EPSG:{utm_epsg(info['lon'], info['lat'])}\n"
    )
    text = FILE.read_text()
    FILE.write_text(text.rstrip("\n") + "\n" + block)
    config.cache_clear()
    return info


# ---- region catalog: what the app's city switcher shows, built from config + the files that exist ----

TIER_ORDER = {"full": 0, "limited": 1}
KM_PER_DEG = 111.195  # km per degree of latitude (mean Earth radius 6371 km)
# Words for a card layer that a limited city may publish; matched against the card file names.
LAYER_WORDS = {"curb_ramps": "curb ramps"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def _words(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _card_stems(root, region: str) -> list[str]:
    d = root / "data" / "cards" / region
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def _listed(root, region: str) -> int | None:
    f = root / "data" / "cards" / "index.csv"
    if not f.exists():
        return None
    total, seen = 0, False
    with f.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row["id"] in (f"{region}.overture_places", f"{region}.osm_destinations"):
                total, seen = total + int(float(row["records"] or 0)), True
    return total if seen else None


def catalog(root=ROOT) -> list[dict]:
    """One dict per visible region: full cities first, then limited ones.

    A region with no cards at all is hidden. Every flag (routes, ratings, detail) is read from the code and
    files that really exist, so the coverage words change when a capability is switched on.
    """
    from . import report_form, routing_ui  # read at call time so a changed flag shows up at once

    out = []
    for rid, c in config("regions").items():
        stems = _card_stems(root, rid)
        if not stems:
            continue
        tier = c.get("tier", "limited")
        has_routes = rid in routing_ui.ROUTING_REGIONS
        has_ratings = rid in report_form.RATING_REGIONS
        f = root / "data" / "map" / f"{rid}_atlas.geojson"
        detail = f.exists()
        if tier == "full":
            coverage = "Places, " + ("routes, " if has_routes else "") + "ratings"
        else:
            extra = [w for key, w in LAYER_WORDS.items() if any(key in st for st in stems)]
            coverage = _words(["Places", *extra]) if extra else "Places only"
        out.append({
            "id": rid,
            "name": c["name"],
            "short": c.get("short", c["name"].split(",")[0]),
            "tier": tier,
            "center": c["center"],
            "bbox": c["bbox"],
            "buffer_km": c["buffer_km"],
            "zoom": c["zoom"],
            "has_routes": has_routes,
            "has_ratings": has_ratings,
            "has_detail": detail or tier == "full",
            "places_detail": len(json.loads(f.read_text())["features"]) if detail else None,
            "places_listed": _listed(root, rid),
            "layers": stems,
            "coverage": coverage,
        })  # fmt: skip
    out.sort(key=lambda r: TIER_ORDER.get(r["tier"], 9))  # stable: yaml order inside a tier
    return out


def notice(region: dict | str, root=ROOT) -> str:
    """Plain-words note for a limited region (empty for a full city). Takes a catalog row or an id."""
    if isinstance(region, str):
        region = next((r for r in catalog(root) if r["id"] == region), None)
        if region is None:
            return ""
    if region["tier"] == "full":
        return ""
    text = region["coverage"] + "."
    if not region["has_ratings"]:
        text += " Ratings not open yet."
    if not region["has_routes"]:
        text += " Routes are not available yet."
    return text


def _grown(r: dict) -> tuple[float, float, float, float]:
    """bbox grown by buffer_km on every side (degrees of longitude use the bbox centre latitude)."""
    s, w, n, e = r["bbox"]
    dlat = r["buffer_km"] / KM_PER_DEG
    dlon = r["buffer_km"] / (KM_PER_DEG * math.cos(math.radians((s + n) / 2)))
    return s - dlat, w - dlon, n + dlat, e + dlon


def closest(lat: float, lon: float, cat: list[dict]) -> str | None:
    """The region that covers a position, or None. Mirrors the rule the device applies in JavaScript.

    Covered = inside the bbox grown by buffer_km. If several cover it, the one the position sits deepest in
    wins: smallest (km to the centre / buffer_km). Plain nearest-centre would send Hamilton, Ohio to Oxford
    because Oxford's buffer is small but its centre is nearer; scaling by the buffer keeps it with Cincinnati.
    """
    best, best_score = None, math.inf
    for r in cat:
        s, w, n, e = _grown(r)
        if s <= lat <= n and w <= lon <= e:
            score = haversine_km(lat, lon, *r["center"]) / r["buffer_km"]
            if score < best_score:
                best, best_score = r["id"], score
    return best
