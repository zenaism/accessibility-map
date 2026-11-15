"""Observation schema v2: the v1 columns plus history, confidence and evidence.

v1 (core.OBS_COLUMNS) stays what the connectors write. `upgrade()` turns a v1 table into v2 without
touching the connectors, so existing data keeps working and releases can ship v2.
Every column is documented in COLUMN_DOCS; docs/data_dictionary.md is generated from it
(`python scripts/make_data_dictionary.py`).
"""

from __future__ import annotations

import pandas as pd

from .core import OBS_COLUMNS, config

SCHEMA_VERSION = "2.0"
V2_EXTRA = [
    "schema_version",
    "source_id",
    "snapshot_date",
    "valid_from",
    "valid_to",
    "confidence",
    "method",
    "evidence",
]
OBS_V2_COLUMNS = OBS_COLUMNS + V2_EXTRA
SIGNALS = {"supports", "limited", "barrier", "unknown"}

# (type, description). v1 columns first, then the new ones.
COLUMN_DOCS: dict[str, tuple[str, str]] = {
    "entity_id": ("string", "Stable id of the thing described: `<source>:<native id>`"),
    "entity_type": (
        "string",
        "poi, path_segment, crossing, kerb, curb_ramp, barrier, entrance, transit_stop, sidewalk_polygon, reported_issue or text",
    ),
    "name": ("string", "Name of the entity, if it has one"),
    "category": ("string", "Source category of the entity (OSM tag, Overture category, and so on)"),
    "attribute": (
        "string",
        "What is being stated (a name from config/attributes.yaml or a street-layer attribute)",
    ),
    "value": ("string", "The stated value (yes, limited, no, unknown, or a measurement)"),
    "signal": ("string", "Meaning for a wheelchair user: supports, limited, barrier or unknown"),
    "source": ("string", "Source id from config/sources.yaml"),
    "source_ref": ("string", "URL or reference of the exact record"),
    "observed_at": ("date", "When the source says the fact was recorded; may be empty"),
    "retrieved_at": ("timestamp", "When we fetched it (UTC)"),
    "license": ("string", "Licence or terms the data came with; decides what we may redistribute"),
    "region": ("string", "Region id from config/regions.yaml"),
    "lat": ("float", "Latitude, WGS84, of a representative point"),
    "lon": ("float", "Longitude, WGS84, of a representative point"),
    "schema_version": ("string", "Schema version this row follows"),
    "source_id": (
        "string",
        "Same as source; kept as its own column so joins to the sources and dataset-card tables are explicit",
    ),
    "snapshot_date": (
        "date",
        "Date of the fetch this row came from (history: a changed value is a new row, never an overwrite)",
    ),
    "valid_from": ("date", "When the fact starts to hold: observed_at if known, else the snapshot date"),
    "valid_to": (
        "date",
        "When it stopped holding; empty while it is the latest value. Expiring facts (events, closures) set it",
    ),
    "confidence": (
        "float",
        "0 to 1: source score x extraction reliability x freshness x corroboration - conflicts (trust.py). Empty if not rated yet",
    ),
    "method": ("string", "How the value was obtained: structured, computed, extracted, manual or crowd"),
    "evidence": (
        "string",
        "Where to check it: the record URL, or a verbatim quote with page or image region for text",
    ),
}

METHOD_BY_TYPE = {
    "arcgis": "structured",
    "socrata": "structured",
    "gtfs": "structured",
    "overpass": "structured",
    "osm_destinations": "structured",
    "osm_entrances": "structured",
    "osm_walk_network": "structured",
    "overture": "structured",
    "slope": "computed",
    "web": "extracted",
    "events_ical": "structured",
    "mura_calendar": "structured",
    "reddit": "crowd",
}


def upgrade(obs: pd.DataFrame, source_scores: dict[str, float] | None = None) -> pd.DataFrame:
    """v1 observations -> v2. `source_scores` maps source id to a 0-100 trust score (see trust.py)."""
    sources = config("sources")
    df = obs.copy()
    df["schema_version"] = SCHEMA_VERSION
    df["source_id"] = df["source"]
    snap = df["retrieved_at"].astype("string").str[:10]
    df["snapshot_date"] = snap
    observed = df["observed_at"].astype("string").str[:10]
    df["valid_from"] = observed.fillna(snap)
    df["valid_to"] = pd.Series([None] * len(df), index=df.index, dtype="string")
    df["method"] = df["source"].map(
        lambda s: METHOD_BY_TYPE.get(sources.get(s, {}).get("type", ""), "structured")
    )
    df["evidence"] = df["source_ref"]
    if source_scores:
        df["confidence"] = df["source"].map(
            lambda s: round(source_scores[s] / 100, 3) if s in source_scores else None
        )
    else:
        df["confidence"] = None
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    return df[OBS_V2_COLUMNS]


def validate(df: pd.DataFrame) -> list[str]:
    """Problems found in a v1 or v2 observation table; empty list = clean."""
    problems = []
    for c in OBS_COLUMNS:
        if c not in df:
            problems.append(f"missing column {c}")
    if problems:
        return problems
    for c in ("entity_id", "attribute", "value", "source", "region"):
        n = int(df[c].isna().sum())
        if n:
            problems.append(f"{n} rows with empty {c}")
    bad = df.loc[df["signal"].notna() & ~df["signal"].isin(SIGNALS), "signal"].unique()
    if len(bad):
        problems.append(f"unknown signal values: {sorted(map(str, bad))}")
    lat, lon = df["lat"].dropna(), df["lon"].dropna()
    if ((lat < -90) | (lat > 90)).any() or ((lon < -180) | (lon > 180)).any():
        problems.append("coordinates out of range")
    if "confidence" in df:
        c = df["confidence"].dropna()
        if ((c < 0) | (c > 1)).any():
            problems.append("confidence outside 0 to 1")
    return problems
