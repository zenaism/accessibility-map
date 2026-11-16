"""Compare two independent sources about the same thing, to measure how far each can be believed (the trust engine's
"agreement" part). Features are matched by position, within a tolerance, in the region's own metric projection.

    python -m atlas.cli agree --region dc      ->  data/cards/agreement_<region>.json  (+ a summary printed)

Two measures per pair, and they are not the same thing:
  corroboration  of what a source CLAIMS, how much does the other source back up (a precision-like number)
  coverage       of what the reference HAS, how much does the other source contain (a completeness-like number)
Absence in a crowd map is not disagreement, so only corroboration feeds the trust score; coverage is reported.
Conflicts (the sources contradict each other at the same place) are listed so they can be checked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

from .core import PROCESSED, ROOT, WGS84, config
from .regions import describe, utm_epsg

CARDS = ROOT / "data" / "cards"
BAD_CONDITION = {"non-compliant", "missing"}
GOOD_CONDITION = {"good", "fair"}


@dataclass
class Matched:
    """For each point of A: distance to the nearest point of B (inf if none within the tolerance) and B's row number."""

    dist: np.ndarray
    idx: np.ndarray

    @property
    def hit(self) -> np.ndarray:
        return np.isfinite(self.dist)


def project(df: pd.DataFrame, region: str) -> np.ndarray:
    d = describe(config("regions")[region]["osm_relation"])
    t = Transformer.from_crs(WGS84, f"EPSG:{utm_epsg(d['lon'], d['lat'])}", always_xy=True)
    x, y = t.transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    return np.column_stack([x, y])


def nearest(a_xy: np.ndarray, b_xy: np.ndarray, tol_m: float) -> Matched:
    if len(a_xy) == 0 or len(b_xy) == 0:
        return Matched(np.full(len(a_xy), np.inf), np.full(len(a_xy), -1))
    dist, idx = cKDTree(b_xy).query(a_xy, distance_upper_bound=tol_m)
    return Matched(np.where(np.isfinite(dist), dist, np.inf), np.where(np.isfinite(dist), idx, -1))


def load(source: str, region: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / region / f"{source}.obs.parquet")


def ramps_vs_osm(
    region: str, osm: str = "osm", inventory: str = "dc_ada_curb_ramps", tol_m: float = 15.0
) -> dict:
    """OSM kerbs tagged lowered or flush (a ramp for a wheelchair) against the official curb-ramp inventory."""
    o = load(osm, region)
    k = o[(o.entity_type == "kerb") & (o.attribute == "kerb")].copy()
    k["v"] = k.value.astype(str).str.lower()
    osm_ramps, osm_raised = k[k.v.isin(["lowered", "flush"])], k[k.v == "raised"]
    inv = load(inventory, region)
    inv = inv.assign(c=inv.value.astype(str).str.lower())
    inv_xy, ramp_xy = project(inv, region), project(osm_ramps, region)
    claims = nearest(ramp_xy, inv_xy, tol_m)  # does the inventory back up each OSM ramp?
    cover = nearest(inv_xy, ramp_xy, tol_m)  # does OSM contain each inventory ramp?
    inv_present = inv.c.isin(GOOD_CONDITION | BAD_CONDITION).to_numpy()
    hit = cover.hit
    conflicts_raised = nearest(project(osm_raised, region), inv_xy, tol_m)
    # contradictions: the inventory rates the ramp missing, OSM says there is a lowered kerb at the same place
    missing_but_osm_lowered = int(((inv.c == "missing").to_numpy() & hit).sum())
    return {
        "tolerance_m": tol_m,
        "osm_lowered_or_flush": int(len(osm_ramps)),
        "osm_corroborated_by_inventory": int(claims.hit.sum()),
        "osm_corroboration": round(float(claims.hit.mean()), 3) if len(osm_ramps) else None,
        "inventory_ramps": int(len(inv)),
        "inventory_in_osm": int(hit.sum()),
        "osm_coverage_of_inventory": round(float(hit.mean()), 3) if len(inv) else None,
        "osm_raised_kerbs": int(len(osm_raised)),
        "osm_raised_where_inventory_has_a_ramp": int(conflicts_raised.hit.sum()),
        "inventory_missing_but_osm_lowered": missing_but_osm_lowered,
        "inventory_noncompliant_and_in_osm": int(((inv.c == "non-compliant").to_numpy() & hit).sum()),
        "inventory_rated": int(inv_present.sum()),
    }


def aps_vs_osm(
    region: str, osm: str = "osm", inventory: str = "dc_ada_audible_signals", tol_m: float = 25.0
) -> dict:
    """OSM crossings tagged with a sound signal against the official inventory of audible pedestrian signals."""
    o = load(osm, region)
    s = o[(o.attribute == "traffic_signals:sound") & (o.value.astype(str).str.lower() == "yes")]
    inv = load(inventory, region)
    inv = inv.assign(c=inv.value.astype(str).str.lower())
    compliant = inv[inv.c.str.contains("compliant version")]
    claims = nearest(project(s, region), project(compliant, region), tol_m)
    cover = nearest(project(compliant, region), project(s, region), tol_m)
    return {
        "tolerance_m": tol_m,
        "osm_sound_signals": int(len(s)),
        "osm_corroborated_by_inventory": int(claims.hit.sum()),
        "osm_corroboration": round(float(claims.hit.mean()), 3) if len(s) else None,
        "inventory_compliant_aps": int(len(compliant)),
        "inventory_in_osm": int(cover.hit.sum()),
        "osm_coverage_of_inventory": round(float(cover.hit.mean()), 3) if len(compliant) else None,
    }


PAIRS = {"dc": {"curb_ramps": ramps_vs_osm, "audible_signals": aps_vs_osm}}


def agreement(region: str) -> dict:
    out = {name: fn(region) for name, fn in PAIRS.get(region, {}).items()}
    CARDS.mkdir(parents=True, exist_ok=True)
    (CARDS / f"agreement_{region}.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def corroboration_for(region: str, source: str) -> float | None:
    """The corroboration share that feeds a source's trust score: only the crowd source (OSM) is judged this way."""
    f = CARDS / f"agreement_{region}.json"
    if source != "osm" or not f.exists():
        return None
    shares = [
        v["osm_corroboration"]
        for v in json.loads(f.read_text()).values()
        if v.get("osm_corroboration") is not None
    ]
    return round(sum(shares) / len(shares), 3) if shares else None
