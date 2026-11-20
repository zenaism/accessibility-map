"""Export the walking network for in-browser routing (src/atlas/web/routing.js).

Python keeps every rule (penalty(), blind_penalty()); the browser only searches and words the result.
Output: data/map/routing/<region>.graph.json, columnar so it gzips well:

  scale   coordinates are integers of degrees x scale (1e7 = OSM's own precision, so bearings match Python)
  lat0    radians; the projection routing.py uses for snapping (x = lon*cos(lat0)*111320, y = lat*111320)
  nodes   {lon: [...], lat: [...]}     delta-encoded integers
  names   street names (including "the X sidewalk" names from routing._name_sidewalks)
  kinds   raw crossing=* values
  edges   parallel arrays: u, v (node indexes), len (m), cost, blind (null = stairs, never used),
          cls (class code, see CLASSES), name (index into names or -1), kind (index into kinds or -1),
          flags (bit field, see FLAGS), grade (percent, one decimal, null = unknown)

Run: python -m atlas.export_routing --region oxford
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

from . import routing
from .core import ROOT

SCALE = 10_000_000
OUT_DIR = ROOT / "data" / "map" / "routing"
# class code -> fallback name used when an edge has no street name (routing._legs)
CLASSES = ["other", "footway", "sidewalk", "crossing", "path", "pedestrian", "service", "cycleway"]
FLAGS = {
    "steep": 1,  # grade above 8.33%
    "roadNoSidewalk": 2,  # a road with no sidewalk mapped (adds 'no sidewalk mapped here')
    "stairs": 4,
    "raisedKerb": 8,
    "crossing": 16,
    "signals": 32,  # signals=yes or crossing=traffic_signals
    "audible": 64,  # sound or vibration = yes
    "tactile": 128,
}
LEN_DECIMALS = 4  # 0.1 mm: JS and Python sum to the same rounded feet


def _class(e: dict) -> int:
    hw, fw = e["highway"], e["footway"]
    if hw == "footway":
        return 2 if fw == "sidewalk" else 3 if fw == "crossing" else 1
    return {"crossing": 3, "path": 4, "pedestrian": 5, "service": 6, "cycleway": 7}.get(hw, 0)


def _flags(e: dict) -> int:
    f = 0
    if e["grade"] is not None and e["grade"] > 8.33:
        f |= FLAGS["steep"]
    if (
        e["highway"] in routing.ROADS
        and e["footway"] is None
        and (e.get("sidewalk") or "")
        in (
            "",
            "no",
            "none",
            "separate",
        )
    ):
        f |= FLAGS["roadNoSidewalk"]
    if e["steps"]:
        f |= FLAGS["stairs"]
    if e.get("raised_kerb"):
        f |= FLAGS["raisedKerb"]
    if routing.is_crossing(e):
        f |= FLAGS["crossing"]
    if e.get("signals") is True or (e.get("crossing") or "") == "traffic_signals":
        f |= FLAGS["signals"]
    if routing._yes(e.get("sound")) or routing._yes(e.get("vibration")):
        f |= FLAGS["audible"]
    if e.get("tactile") is True:
        f |= FLAGS["tactile"]
    return f


def _delta(vals: list[int]) -> list[int]:
    return [v - p for v, p in zip(vals, [0, *vals[:-1]], strict=True)]


def build(region: str) -> dict:
    """The graph as a JSON-ready dict (deterministic: same input gives identical output)."""
    g, nodes, _, lat0 = routing.network(region)
    index = {int(n): i for i, n in enumerate(nodes.node_id)}
    names: dict[str, int] = {}
    kinds: dict[str, int] = {}
    cols = {k: [] for k in ("u", "v", "len", "cost", "blind", "cls", "name", "kind", "flags", "grade")}
    for a, b, e in sorted(g.edges(data=True), key=lambda t: (index[t[0]], index[t[1]])):
        cols["u"].append(index[a])
        cols["v"].append(index[b])
        cols["len"].append(round(e["length_m"], LEN_DECIMALS))
        finite = math.isfinite(e["cost"])
        cols["cost"].append(round(e["cost"], LEN_DECIMALS) if finite else None)
        cols["blind"].append(round(e["cost_blind"], LEN_DECIMALS) if finite else None)
        cols["cls"].append(_class(e))
        cols["name"].append(names.setdefault(e["name"], len(names)) if e["name"] else -1)
        k = e.get("crossing")
        cols["kind"].append(kinds.setdefault(k, len(kinds)) if k else -1)
        cols["flags"].append(_flags(e))
        cols["grade"].append(None if e["grade"] is None else round(e["grade"], 1))
    return {
        "version": 1,
        "region": region,
        "scale": SCALE,
        "lat0": lat0,
        "classes": CLASSES,
        "flags": FLAGS,
        "nodes": {
            "lon": _delta([round(x * SCALE) for x in nodes.lon]),
            "lat": _delta([round(x * SCALE) for x in nodes.lat]),
        },
        "names": list(names),
        "kinds": list(kinds),
        "edges": cols,
    }


def write(region: str, out_dir: Path = OUT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build(region)
    raw = json.dumps(data, separators=(",", ":"), allow_nan=False).encode()
    path = out_dir / f"{region}.graph.json"
    path.write_bytes(raw)
    gz = len(gzip.compress(raw, 9, mtime=0))
    info = {
        "path": str(path),
        "nodes": len(data["nodes"]["lon"]),
        "edges": len(data["edges"]["u"]),
        "raw_bytes": len(raw),
        "gzip_bytes": gz,
    }
    print(
        f"{region}: {info['nodes']:,} nodes, {info['edges']:,} edges -> {path}\n"
        f"  raw {len(raw) / 1e6:.2f} MB, gzipped {gz / 1e6:.2f} MB"
    )
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="oxford")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    write(args.region, args.out)


if __name__ == "__main__":
    main()
