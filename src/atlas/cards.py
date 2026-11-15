"""Dataset cards: one machine-readable description of every source and region we hold.

    python -m atlas.cli cards     ->  data/cards/<region>/<source>.json  +  data/cards/index.csv

Rebuilt from the files on disk and config/sources.yaml (nothing typed by hand). A card says what a
dataset contains, how much, how fresh and how complete it is, and carries its trust rating, so we
can compute things like coverage per region without opening the data.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import pyarrow.parquet as pq

from . import trust
from .core import PROCESSED, RAW, ROOT, config

CARDS = ROOT / "data" / "cards"
SCHEMA = "atlas.dataset_card/1"


def _web_manifest(source: str) -> tuple[int, int, int]:
    """(failed, robots skipped, fetched) from the raw download log of a web source."""
    f = RAW / "web" / source / "manifest.jsonl"
    if not f.exists():
        return 0, 0, 0
    recs = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    robots = sum(1 for r in recs if str(r.get("status", "")).startswith("robots"))
    failed = sum(1 for r in recs if not r.get("file") and not str(r.get("status", "")).startswith("robots"))
    return failed, robots, sum(1 for r in recs if r.get("file"))


def _obs_stats(path: Path) -> dict:
    o = pd.read_parquet(path)
    key = ["entity_id", "attribute", "value"]
    lat, lon = o["lat"].dropna(), o["lon"].dropna()
    return {
        "observations": len(o),
        "attributes": dict(Counter(o["attribute"]).most_common(12)),
        "null_rates": {
            c: round(float(o[c].isna().mean()), 4)
            for c in ("value", "attribute", "lat", "lon", "observed_at")
        },
        "duplicates_share": round(float(o.duplicated(key).mean()), 4),
        "bbox": [
            round(float(lon.min()), 5),
            round(float(lat.min()), 5),
            round(float(lon.max()), 5),
            round(float(lat.max()), 5),
        ]
        if len(lat)
        else None,
        "observed_range": [
            str(o["observed_at"].dropna().min())[:10],
            str(o["observed_at"].dropna().max())[:10],
        ]
        if o["observed_at"].notna().any()
        else None,
        "last_retrieved": str(o["retrieved_at"].dropna().max())[:10]
        if o["retrieved_at"].notna().any()
        else None,
    }


def _quality(card: dict) -> float | None:
    """Share of usable rows: values present, locations present where the source has them, few duplicates."""
    if card["observations"]:
        n = card["null_rates"]
        parts = [1 - n["value"], 1 - n["attribute"], 1 - card["duplicates_share"]]
        if card["bbox"] is not None:
            parts.append(1 - max(n["lat"], n["lon"]))
        return round(sum(parts) / len(parts), 3)
    if card["documents"] or card["events"]:
        return 1.0
    return None


def _completeness(card: dict) -> float | None:
    if not card["collected"]:
        return None
    fetched = card.get("pages_fetched", 0)
    failed = card["failed_fetches"]
    if card["connector"] == "web" and fetched + failed:
        return round(fetched / (fetched + failed), 3)
    return 1.0


def _issues(card: dict, exp: int) -> list[str]:
    out = []
    t = card["trust"]
    if not card["licence"]:
        out.append("no licence recorded: do not redistribute")
    if card["age_days"] is not None and card["age_days"] > exp:
        out.append(f"older than its refresh interval ({card['age_days']} days vs {exp})")
    if card["failed_fetches"]:
        out.append(f"{card['failed_fetches']} pages failed to fetch")
    if card["robots_skipped"]:
        out.append(f"{card['robots_skipped']} pages skipped because robots.txt asks bots not to fetch them")
    if card["duplicates_share"] and card["duplicates_share"] > 0.05:
        out.append(f"{card['duplicates_share']:.0%} duplicate rows")
    if t["tier"] in ("C", "D"):
        out.append(f"low trust (tier {t['tier']}): not used for answers")
    return out


def build_card(source: str, spec: dict, region: str) -> dict:
    d = PROCESSED / region
    ent, obs = d / f"{source}.entities.parquet", d / f"{source}.obs.parquet"
    docs, events = d / f"{source}.docs.parquet", d / f"{source}.events.parquet"
    card = {
        "schema": SCHEMA,
        "id": f"{region}.{source}",
        "source": source,
        "region": region,
        "title": source.replace("_", " "),
        "connector": spec["type"],
        "publisher": urlparse(spec.get("url", "")).netloc or None,
        "url": spec.get("url") or None,
        "licence": spec.get("license") or None,
        "collected": any(p.exists() for p in (ent, obs, docs, events)),
        "entities": pq.ParquetFile(ent).metadata.num_rows if ent.exists() else 0,
        "observations": 0,
        "documents": 0,
        "events": 0,
        "attributes": {},
        "null_rates": {},
        "duplicates_share": 0.0,
        "bbox": None,
        "observed_range": None,
        "last_retrieved": None,
    }
    if obs.exists():
        card.update(_obs_stats(obs))
    if docs.exists():
        x = pd.read_parquet(docs, columns=["retrieved_at"])
        card["documents"] = len(x)
        card["last_retrieved"] = (
            str(x.retrieved_at.dropna().max())[:10] if x.retrieved_at.notna().any() else None
        )
    if events.exists():
        e = pd.read_parquet(events, columns=["retrieved_at"])
        card["events"] = len(e)
        card["last_retrieved"] = (
            str(e.retrieved_at.dropna().max())[:10] if e.retrieved_at.notna().any() else None
        )
    failed, robots, fetched = _web_manifest(source)
    card.update(failed_fetches=failed, robots_skipped=robots, pages_fetched=fetched)
    if card["last_retrieved"] is None and card["collected"]:
        newest = max(p.stat().st_mtime for p in (ent, obs, docs, events) if p.exists())
        card["last_retrieved"] = pd.Timestamp(newest, unit="s").strftime("%Y-%m-%d")
    card["age_days"] = trust.age_days(card["last_retrieved"])
    exp = trust.refresh_days(spec["type"])
    card["refresh_days"] = exp
    comps = {
        "authority": trust.authority(spec["type"], source),
        "provenance": trust.provenance(
            card["licence"], card["url"] or card["publisher"], card["last_retrieved"]
        ),
        "freshness": trust.freshness(card["age_days"], exp),
        "completeness": _completeness(card),
        "quality": _quality(card),
        "agreement": None,  # needs the fusion step
        "track_record": None,  # needs reference data
    }
    card["trust"] = trust.source_score(comps) if card["collected"] else None
    if card["trust"] and not card["licence"]:
        card["trust"] = trust.cap_tier(card["trust"], "B", "no licence recorded")
    if card["trust"] is None:
        card["trust"] = {"score": 0.0, "tier": "D", "components": comps, "used": []}
        card["known_issues"] = ["not collected yet"]
    else:
        card["known_issues"] = _issues(card, exp)
    return card


def build_all() -> list[dict]:
    cards = []
    for source, spec in config("sources").items():
        for region in spec["regions"]:
            cards.append(build_card(source, spec, region))
    return cards


def write() -> Path:
    cards = build_all()
    for c in cards:
        out = CARDS / c["region"]
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{c['source']}.json").write_text(json.dumps(c, indent=2, default=str) + "\n")
    rows = [
        {
            "id": c["id"],
            "connector": c["connector"],
            "collected": c["collected"],
            "records": c["entities"] or c["documents"] or c["events"],
            "observations": c["observations"],
            "licence": c["licence"],
            "last_retrieved": c["last_retrieved"],
            "age_days": c["age_days"],
            "trust_score": c["trust"]["score"],
            "tier": c["trust"]["tier"],
            "issues": "; ".join(c["known_issues"]),
        }
        for c in cards
    ]
    idx = CARDS / "index.csv"
    pd.DataFrame(rows).to_csv(idx, index=False)
    return idx
