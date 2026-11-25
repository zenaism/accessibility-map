"""Write tests/js/regions_golden.json: sample positions and the region the Python rule picks.

The browser implements the same rule in JavaScript (inside bbox grown by buffer_km; deepest wins) and tests
itself against this file. Regenerate after changing config/regions.yaml:
    PYTHONPATH=src python scripts/make_regions_golden.py
"""

import json
from pathlib import Path

from atlas.regions import catalog, closest

ROOT = Path(__file__).resolve().parent.parent
POINTS = [  # (label, lat, lon)
    ("Oxford, Miami University campus", 39.5070, -84.7452),
    ("Downtown Cincinnati", 39.1031, -84.5120),
    ("Hamilton, Ohio (inside the Cincinnati buffer)", 39.3995, -84.5613),
    ("Columbus, Ohio", 39.9612, -82.9988),
    ("Downtown Dayton", 39.7589, -84.1916),
    ("Washington, DC", 38.8977, -77.0365),
    ("Baltimore (hidden)", 39.2904, -76.6122),
    ("Middle of the Atlantic", 30.0, -40.0),
    ("Cincinnati airport side (Kentucky)", 39.0489, -84.6678),
    ("Springboro, Ohio (between Dayton and Cincinnati)", 39.5523, -84.2333),
]

if __name__ == "__main__":
    cat = catalog()
    rows = [
        {"label": label, "lat": lat, "lon": lon, "expected": closest(lat, lon, cat)}
        for label, lat, lon in POINTS
    ]
    out = ROOT / "tests" / "js" / "regions_golden.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + "\n")
    keep = ("id", "short", "tier", "center", "bbox", "buffer_km")
    slim = [{k: r[k] for k in keep} for r in cat]
    (out.parent / "regions_catalog.json").write_text(json.dumps(slim, indent=1) + "\n")
    print(out, len(rows))
