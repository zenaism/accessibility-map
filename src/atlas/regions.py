"""Region resolver: find a place's OSM boundary, check it, and pin it in config/regions.yaml.

    python -m atlas.cli region search "Dayton, Ohio"
    python -m atlas.cli region add dayton "Dayton, Ohio" --relation 182954 --buffer-km 20

A region is always a pinned OpenStreetMap relation id, never matched by name (the predecessor project matched
"Manhattan" to Manhattan, Kansas). `search` lists the candidates with their area so a wrong match is obvious;
`add` refuses a boundary whose area is implausible for a city and appends the entry (comments are kept).
"""

from __future__ import annotations

import json
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
