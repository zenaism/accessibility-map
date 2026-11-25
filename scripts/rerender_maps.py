"""Re-render the three map pages with the current page template, keeping the data already inside them.

    python scripts/rerender_maps.py

Use this when only the page itself changed (design, report form): `make map` also rebuilds all the data and can change
hundreds of files. The data, title and navigation are read back out of the existing pages, so nothing else changes.
"""

import json
import re
from pathlib import Path

from atlas.map_viewer import render

ROOT = Path(__file__).resolve().parents[1]
for name in ("index", "cincinnati", "oxford"):
    f = ROOT / "data" / "map" / f"{name}.html"
    old = f.read_text()
    title = re.search(r"<title>(.*?) · Accessibility Map</title>", old).group(1)
    m = re.search(r'<span id="asof"></span>(.*?)</p></div>', old, re.S)
    nav = m.group(1) if m else ""
    if "window.__MAPDATA=" in old:  # a page of the new map app
        raw = old.split("window.__MAPDATA=", 1)[1].split(";</script>", 1)[0]
    else:
        raw = old.split("const DATA = ", 1)[1].split(", RATINGS = ", 1)[0]
    data = json.loads(raw.replace("\\u003c", "<"))
    new = render(data, title, nav)
    f.write_text(new)
    print(f"{name}.html: {len(old):,} -> {len(new):,} characters")
