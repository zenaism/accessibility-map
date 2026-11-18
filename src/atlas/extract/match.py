"""Tie extracted facts to places on the map (docs/system_overview.md: entity matching of text facts).

    python scripts/match_facts.py <source> --region <r>   ->  data/processed/<r>/<source>.fact_places.parquet

Two ways, in this order:
  1. seed:  the page belongs to a website that came from a place (place-driven crawl): the place is known, score 1.
  2. name:  the page or section title names a place on the map. Accepted only when the name is specific (two or more
            distinctive words), matches closely, and no other place matches almost as well. Everything else stays unmatched:
            a wrong link is worse than no link.
A person (or the position check below) can still reject a match; the score and the method are stored with it.
"""

from __future__ import annotations

import re

import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz

from ..core import PROCESSED

GENERIC = frozenset(
    [
        "the",
        "of",
        "and",
        "at",
        "in",
        "on",
        "for",
        "a",
        "an",
        "to",
        "from",
        "library",
        "school",
        "center",
        "centre",
        "museum",
        "park",
        "station",
        "hall",
        "building",
        "office",
        "church",
        "restaurant",
        "cafe",
        "coffee",
        "bar",
        "pub",
        "grill",
        "shop",
        "store",
        "market",
        "inn",
        "hotel",
        "house",
        "club",
        "department",
        "city",
        "county",
        "university",
        "college",
        "home",
        "page",
        "about",
        "contact",
        "welcome",
        "accessibility",
        "access",
        "visit",
        "hours",
        "info",
        "information",
        "services",
        "service",
    ]
)
MIN_SCORE, MIN_GAP = 94, 6


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", re.sub(r"%20|_", " ", (s or "").lower()).replace("’", "'"))


def distinctive(s: str) -> list[str]:
    return [t for t in tokens(s) if t not in GENERIC and len(t) > 1]


def candidates_from_title(title: str) -> list[str]:
    """'Opening hours | Oxford Lane Library' -> ['Opening hours', 'Oxford Lane Library'] (each part may be the place)."""
    parts = [p.strip() for p in re.split(r"\s[|–—-]\s|:\s", title or "") if p.strip()]
    return list(dict.fromkeys([title or "", *parts]))


def places(region: str) -> pd.DataFrame:
    frames = []
    for n in ("overture_places", "osm_destinations"):
        f = PROCESSED / region / f"{n}.entities.parquet"
        if f.exists():
            g = gpd.read_parquet(f)
            g = g[g.name.notna() & (g.name.astype(str).str.len() > 3)]
            frames.append(g[["entity_id", "name"]].assign(layer=n))
    out = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["entity_id", "name", "layer"])
    )
    out["key"] = out.name.map(lambda s: " ".join(tokens(s)))
    return out.drop_duplicates("key")


def best(title: str, pl: pd.DataFrame) -> tuple[str, str, int] | None:
    """(entity_id, name, score) of the one place this title names, or None."""
    top = None
    for cand in candidates_from_title(title):
        key = " ".join(tokens(cand))
        if len(tokens(key)) < 2:
            continue
        # the whole title part must look like the whole place name
        scores = pd.Series([fuzz.ratio(key, k) for k in pl.key], index=pl.index)
        order = scores.sort_values(ascending=False)
        if order.iloc[0] < MIN_SCORE:
            continue
        row = pl.loc[order.index[0]]
        if len(distinctive(row["name"])) < 1 or len(tokens(row["name"])) < 2:
            continue  # a one-word name such as "Starbucks" or "Park" is too weak to link by title alone
        second = order.iloc[1] if len(order) > 1 else 0
        if order.iloc[0] - second < MIN_GAP and second >= MIN_SCORE:
            continue  # two places match equally well (two branches): do not guess
        if top is None or order.iloc[0] > top[2]:
            top = (row["entity_id"], row["name"], int(order.iloc[0]))
    return top


def link(facts: pd.DataFrame, region: str) -> pd.DataFrame:
    """One row per fact: entity_id, entity_name, match_score, match_method (empty when no place is named)."""
    pl = places(region)
    cache: dict[str, tuple | None] = {}
    out = []
    for r in facts.itertuples():
        pid = getattr(r, "place_id", None)
        if isinstance(pid, str) and pid:
            out.append((pid, r.place, 100, "seed"))
            continue
        if r.place not in cache:
            cache[r.place] = best(r.place, pl) if len(pl) else None
        m = cache[r.place]
        out.append((m[0], m[1], m[2], "name") if m else (None, None, None, None))
    res = pd.DataFrame(
        out, columns=["entity_id", "entity_name", "match_score", "match_method"], index=facts.index
    )
    return pd.concat([facts[["doc_id", "url", "place", "attribute", "value", "evidence_quote"]], res], axis=1)


def run(source: str, region: str) -> pd.DataFrame:
    facts = pd.read_parquet(PROCESSED / region / f"{source}.facts.parquet")
    out = link(facts, region)
    out.to_parquet(PROCESSED / region / f"{source}.fact_places.parquet", index=False)
    return out
