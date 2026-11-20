"""Write tests/golden_routes_<region>.json: start/destination pairs run through the Python routing.route()
for both profiles. The JavaScript port (src/atlas/web/routing.js, directions.js) must reproduce them.

Pairs are chosen deterministically from the places in data/map/<region>_atlas.geojson so that every kind
of route is covered (stairs avoided, steep, many crossings, no sidewalk, too far, no route, same point).
The chosen coordinates are written into the golden file, so the tests do not depend on this selection.

Run: PYTHONPATH=src python scripts/make_golden_routes.py --region oxford
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import networkx as nx

from atlas import routing
from atlas.core import ROOT

N_PAIRS = 20


def places(region: str) -> list[tuple[str, float, float]]:
    d = json.loads((ROOT / "data" / "map" / f"{region}_atlas.geojson").read_text())
    return [
        (f["properties"]["name"], f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0])
        for f in d["features"]
        if f["geometry"]["type"] == "Point"
    ]


def node_path(region: str, a: tuple[float, float], b: tuple[float, float], profile: str):
    """Node-index path exactly as routing.route() computes it (None when route() gives None)."""
    g, nodes, _, _ = routing.network(region)
    index = {int(n): i for i, n in enumerate(nodes.node_id)}
    na, _ = routing._snap(region, *a)
    nb, _ = routing._snap(region, *b)
    p = nx.shortest_path(g, na, nb, weight="cost_blind" if profile == "blind" else "cost")
    return [index[n] for n in p]


def run(region: str, a, b) -> dict:
    out = {}
    for profile in ("wheelchair", "blind"):
        r = routing.route(region, a[0], a[1], b[0], b[1], profile)
        if r is None:
            _, da = routing._snap(region, *a)
            _, db = routing._snap(region, *b)
            reason = "too_far" if max(da, db) > 150 else "no_step_free_route"
            out[profile] = {"result": None, "reason": reason, "path": None}
            continue
        r = {k: v for k, v in r.items() if k not in ("line", "note")}
        out[profile] = {"result": r, "reason": None, "path": node_path(region, a, b, profile)}
    return out


def pick(region: str) -> list[dict]:
    pts = places(region)
    rnd = random.Random(20261120)
    lat0 = math.radians(sum(p[1] for p in pts) / len(pts))

    def dist(a, b):
        return math.hypot((a[2] - b[2]) * math.cos(lat0) * 111320, (a[1] - b[1]) * 111320)

    cands = []
    for _ in range(500):
        a, b = rnd.sample(pts, 2)
        dm = dist(a, b)
        if not 30 < dm < 2600:
            continue
        r = routing.route(region, a[1], a[2], b[1], b[2])
        bl = routing.route(region, a[1], a[2], b[1], b[2], "blind") if r else None
        cands.append((a, b, dm, r, bl))

    wanted = [  # (category, how many, predicate)
        ("avoids stairs", 3, lambda c: c[3] and "stair" in c[3]["compared_with_shortest"]),
        ("steep sections", 2, lambda c: c[3] and c[3]["steep_sections"] >= 2),
        ("many crossings", 3, lambda c: c[3] and c[3]["crossings"]["total"] >= 10),
        (
            "blind route differs",
            2,
            lambda c: (
                c[3]
                and c[4]
                and c[3]["crossings"]["total"] >= 3
                and c[3]["steps"] == 0
                and c[4]["directions"] != c[3]["directions"]
            ),
        ),
        ("road without sidewalk", 1, lambda c: c[3] and c[3]["road_without_sidewalk_feet"] > 50),
        ("raised kerb", 1, lambda c: c[3] and c[3]["raised_kerbs"] > 0),
        ("short, no crossings", 2, lambda c: c[3] and c[3]["crossings"]["total"] == 0 and c[2] < 300),
        ("long", 1, lambda c: c[3] and c[2] > 1900),
        (
            "no route",
            2,
            lambda c: (
                c[3] is None
                and max(
                    routing._snap(region, c[0][1], c[0][2])[1], routing._snap(region, c[1][1], c[1][2])[1]
                )
                <= 150
            ),
        ),
        (
            "shortest is also easiest",
            1,
            lambda c: c[3] and c[3]["compared_with_shortest"].startswith("This is"),
        ),
    ]
    chosen, used = [], set()
    for cat, n, ok in wanted:
        got = 0
        for c in cands:
            key = (c[0][0], c[1][0])
            if key in used or not ok(c):
                continue
            used.add(key)
            chosen.append((cat, c[0], c[1]))
            got += 1
            if got == n:
                break
    pairs = [
        {"label": f"{a[0]} -> {b[0]}", "category": cat, "from": [a[1], a[2]], "to": [b[1], b[2]]}
        for cat, a, b in chosen
    ]
    here = ("", *pairs[0]["from"])
    pairs.append(
        {
            "label": "same point",
            "category": "same point",
            "from": [here[1], here[2]],
            "to": [here[1], here[2]],
        }
    )
    pairs.append(
        {
            "label": "start far from any path",
            "category": "too far",
            "from": [39.0, -84.0],
            "to": [pts[1][1], pts[1][2]],
        }
    )
    pairs.append(
        {
            "label": "destination far from any path",
            "category": "too far",
            "from": [pts[1][1], pts[1][2]],
            "to": [39.9, -84.9],
        }
    )
    return pairs[:N_PAIRS] if len(pairs) > N_PAIRS else pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="oxford")
    args = ap.parse_args()
    pairs = pick(args.region)
    for p in pairs:
        p["results"] = run(args.region, p["from"], p["to"])
    out = {"region": args.region, "n_pairs": len(pairs), "pairs": pairs}
    path = Path(ROOT / "tests" / f"golden_routes_{args.region}.json")
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(pairs)} pairs -> {path} ({path.stat().st_size / 1024:.0f} KB)")
    for p in pairs:
        w = p["results"]["wheelchair"]
        print(f"  {p['category']:<26} {p['label'][:60]:<60} {w['reason'] or w['result']['length_feet']}")


if __name__ == "__main__":
    main()
