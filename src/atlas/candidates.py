"""Candidate sources found by automatic discovery, and the rules that accept or reject them.

    python -m atlas.cli candidates    ->  rates every candidate and updates data/candidates/source_candidates.csv

States (docs/architecture.md section 8): new -> triaged -> approved | quarantined | rejected -> ingested -> stale -> retired.
Nobody approves by hand: the trust engine scores the metadata (authority, provenance, freshness) and the tier decides.
A candidate that passes is only *approved*; it becomes *ingested* when a connector has fetched it.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd

from . import trust
from .core import ROOT

FILE = ROOT / "data" / "candidates" / "source_candidates.csv"
STATES = ["new", "triaged", "approved", "quarantined", "rejected", "ingested", "stale", "retired"]
COLUMNS = [
    "candidate_id", "url", "title", "publisher", "region", "route", "authority_kind", "licence", "data_year",
    "state", "score", "tier", "reason", "added_at", "updated_at",
]  # fmt: skip
TIER_STATE = {"A": "approved", "B": "approved", "C": "quarantined", "D": "rejected"}
# open licences we can accept for redistribution; anything else lowers provenance
OPEN = ("cc0", "cc by", "cc-by", "public domain", "odbl", "apache", "cdla", "open")


def candidate_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def licence_score(licence: str | None) -> float:
    """1 for a clearly open licence, 0.5 when stated but not clearly open, 0 when unknown."""
    if not licence or licence.lower().startswith(("unknown", "unclear", "none")):
        return 0.0
    return 1.0 if any(k in licence.lower() for k in OPEN) else 0.5


def score(row: dict, today: date | None = None) -> dict:
    """Score a candidate from its metadata alone (nothing has been fetched yet)."""
    year = row.get("data_year")
    age = None if pd.isna(year) or not year else ((today or date.today()).year - int(year)) * 365
    comps = {
        "authority": trust.authority(kind=row.get("authority_kind") or "unknown"),
        "provenance": round(0.5 * licence_score(row.get("licence")) + 0.5 * bool(row.get("url")), 3),
        "freshness": trust.freshness(
            age, 365 * 3
        ),  # inventories are expected to be refreshed within about 3 years
        "completeness": None,
        "quality": None,
        "agreement": None,
        "track_record": None,
    }
    return trust.source_score(comps)


def load() -> pd.DataFrame:
    return pd.read_csv(FILE) if FILE.exists() else pd.DataFrame(columns=COLUMNS)


def add(df: pd.DataFrame, **c) -> pd.DataFrame:
    """Add a candidate if its URL is not already known."""
    cid = candidate_id(c["url"])
    if (df["candidate_id"] == cid).any():
        return df
    today = date.today().isoformat()
    row = {k: c.get(k) for k in COLUMNS} | {
        "candidate_id": cid,
        "state": "new",
        "added_at": today,
        "updated_at": today,
    }
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def rate(df: pd.DataFrame) -> pd.DataFrame:
    """Score every candidate still in `new` or `triaged` and move it to approved, quarantined or rejected."""
    df = df.copy()
    for i, r in df.iterrows():
        if r["state"] not in ("new", "triaged"):
            continue
        s = score(r.to_dict())
        if licence_score(r.get("licence")) == 0:
            s = trust.cap_tier(s, "B", "licence unknown or unclear: may be used, not redistributed")
        df.loc[i, ["score", "tier", "state", "updated_at"]] = [
            s["score"],
            s["tier"],
            TIER_STATE[s["tier"]],
            date.today().isoformat(),
        ]
        df.loc[i, "reason"] = (
            "used: " + ", ".join(s["used"]) + (f"; {s['capped']}" if s.get("capped") else "")
        )
    return df


def save(df: pd.DataFrame) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    df.reindex(columns=COLUMNS).to_csv(FILE, index=False)


# First candidates found while researching Washington DC, Maryland and Dayton (docs/source_types.md section 4).
SEEDS = [
    dict(url="https://catalog.data.gov/dataset/ada-curb-ramp", title="DC ADA Curb Ramp (2016 transition plan inventory)", publisher="DDOT / DCGIS", region="dc", route="A", authority_kind="official_inventory", licence="CC BY 4.0", data_year=2016),
    dict(url="https://catalog.data.gov/dataset/ada-driveway", title="DC ADA Driveway (2016 transition plan inventory)", publisher="DDOT / DCGIS", region="dc", route="A", authority_kind="official_inventory", licence="CC BY 4.0", data_year=2016),
    dict(url="https://catalog.data.gov/dataset/sidewalk-ramps-2010", title="DC Sidewalk Ramps 2010 (planimetric polygons)", publisher="DC GIS", region="dc", route="A", authority_kind="official_inventory", licence="", data_year=2010),
    dict(url="https://sidewalk-dc.cs.washington.edu", title="Project Sidewalk, DC deployment (crowd labels)", publisher="UW Makeability Lab", region="dc", route="A", authority_kind="crowd", licence="CC0 1.0", data_year=None),
    dict(url="https://maps.roads.maryland.gov/arcgis/rest/services/OHD_ADA/PedestrianFacilities_Maryland_MDOTSHA/MapServer", title="MDOT SHA Pedestrian Facilities (ramps, sidewalks, bus stops on state roads)", publisher="MDOT State Highway Administration", region="maryland", route="A", authority_kind="official_inventory", licence="", data_year=None),
    dict(url="https://catalog.data.gov/dataset/its4us-demonstration-region-data-on-the-tdei", title="OpenSidewalks / TDEI demonstration data (Baltimore and Montgomery counties)", publisher="UW Taskar Center", region="maryland", route="A", authority_kind="open_dataset", licence="unclear (CC0 in one record, other in another)", data_year=None),
    dict(url="https://daytonohio.gov/DocumentCenter/View/13774/Dayton-ADA-SETP-Public-Review-Version", title="City of Dayton ADA Self-Evaluation and Transition Plan (PDF)", publisher="City of Dayton", region="dayton", route="B", authority_kind="official_site", licence="", data_year=2023),
    dict(url="https://tims.dot.state.oh.us/ags/rest/services/MapViewers/ADA_Sidewalk_Inventory/MapServer", title="ODOT ADA Sidewalk Inventory (statewide, state routes)", publisher="Ohio DOT", region="dayton", route="A", authority_kind="official_inventory", licence="", data_year=2026),
]  # fmt: skip


def seed() -> pd.DataFrame:
    df = load()
    for s in SEEDS:
        df = add(df, **s)
    return df
