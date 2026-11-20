# ruff: noqa: E501
"""Export the assistant's data for the browser (guided mode): places, facts with quote/source/date,
events, precomputed conditions around each place and named area, per region, plus the shared rules.

    python -m atlas.export_assistant_data            # -> data/map/assistant/<region>.json + rules.json

Only public map data goes out (the same facts the map pages show); nothing private. The file for a
region holds compact arrays so it stays small (the size is printed; the limit for committing is 1.5 MB
per region). Place order is the knowledge-base order, which the JavaScript tools rely on for ties.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .assistant import rules as R
from .assistant import tools as T
from .assistant.kb import SITE, connect
from .core import ROOT

OUT = ROOT / "data/map/assistant"
LIMIT_BYTES = 1_500_000


def _slim_route(r: dict | None) -> dict | None:
    if not r:
        return None
    keep = ("length_feet", "crossings_text", "directions", "compared_with_shortest", "from", "to")
    out = {k: r[k] for k in keep if k in r}
    if r.get("blind"):
        out["blind"] = _slim_route(
            {**r["blind"], "from": r.get("from"), "to": r.get("to")}
            if "from" not in r["blind"]
            else r["blind"]
        )
    return out


def key_of(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def export(out: Path = OUT, with_areas: bool = True) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    con = connect()
    cur = con.execute("SELECT * FROM places ORDER BY rowid")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
    facts = con.execute(
        "SELECT link_id, attribute, value, detail, quote, source, date FROM facts ORDER BY rowid"
    ).fetchall()
    events = con.execute(
        "SELECT link_id, title, start, url, access, accessible_tag, disability_focused FROM events ORDER BY rowid"
    ).fetchall()
    generated = max(r["generated"] for r in rows if r["generated"])
    sizes = {}
    for region in R.REGION_KEYS:
        mine = [r for r in rows if r["region"] == region]
        ids = {r["link_id"] for r in mine}
        places = []
        for r in mine:
            gt = json.loads(r["getting_there"]) if r["getting_there"] else {}
            page = r["page"]
            p = {
                "id": r["link_id"],
                "name": r["name"],
                "layer": r["layer"],
                "rating": r["rating"],
                "lat": r["lat"],
                "lon": r["lon"],
                "summary": r["summary"] or "",
                "notice": r["notice"],
                "keys": json.loads(r["keys"]),
                "newest_source": r["newest_source"],
                "address": r.get("address"),
                "phone": r.get("phone"),
                "website": r.get("website"),
                "hours": r.get("hours"),
                "arrival": gt.get("arrival"),
                "route": _slim_route(gt.get("route")),
            }
            if not page.startswith(SITE):
                p["page"] = page
            places.append({k: v for k, v in p.items() if v not in (None, "", [])} | {"keys": p["keys"]})
        local = {r["link_id"]: i for i, r in enumerate(mine)}
        fx = [[local[f[0]], *f[1:]] for f in facts if f[0] in ids]
        ev = [[local[e[0]], e[1], e[2], e[3], e[4], int(e[5]), int(e[6])] for e in events if e[0] in ids]
        lats = [r["lat"] for r in mine if r["lat"] is not None and r["layer"] != "restroom"]
        lons = [r["lon"] for r in mine if r["lon"] is not None and r["layer"] != "restroom"]
        data = {
            "region": region,
            "generated": generated,
            "site": SITE,
            "center": [round(sum(lats) / len(lats), 4), round(sum(lons) / len(lons), 4)] if lats else None,
            "places": places,
            "facts": fx,
            "events": ev,
            "areas": {},
        }
        if with_areas:
            pts = {(r["lat"], r["lon"]) for r in mine if r["lat"] is not None and r["layer"] != "restroom"}
            pts |= {(a["lat"], a["lon"]) for a in R.AREAS.values() if a["region"] == region}
            for lat, lon in sorted(pts):
                c = T.area_conditions(lat, lon, region=region)
                data["areas"][key_of(lat, lon)] = {k: v for k, v in c.items() if k != "note"} | {
                    "note": c["note"]
                }
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        (out / f"{region}.json").write_text(text)
        sizes[region] = len(text.encode())
    (out / "rules.json").write_text(R.rules_json())
    sizes["rules"] = (out / "rules.json").stat().st_size
    return sizes


if __name__ == "__main__":
    sz = export()
    for k, v in sz.items():
        flag = "" if v < LIMIT_BYTES else "  (over 1.5 MB: keep untracked)"
        print(f"data/map/assistant/{k}.json  {v / 1024:.0f} KB{flag}")
    if any(v >= LIMIT_BYTES for v in sz.values()):
        sys.exit(0)
