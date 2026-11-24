"""The Directions panel of the map (CSS + JavaScript, inserted into the map page by map_viewer.py).

The panel and its search are plain files in src/atlas/web/: routing.js (search), directions.js (words),
panel.js (interface), panel.css. This module reads them once and exposes:

  CSS   panel.css
  JS    ROUTING_CORE_SRC (routing.js + directions.js as a string, for the Web Worker) + panel.js + the
        glue that starts the panel with the map page's own objects
  CONFIG  which regions have a walking graph and where the graph files are

Regions listed in ROUTING_REGIONS get the panel and "Route here"; other regions keep the Google Maps link.
The graph files (data/map/routing/<region>.graph.json) are built by `python -m atlas.export_routing`
and are not committed.
"""

from __future__ import annotations

import json
from pathlib import Path

WEB = Path(__file__).with_name("web")
# Cincinnati is measured and works (4.3 MB gzipped graph) but is off on this deploy branch:
# add "cincinnati" here, run `python -m atlas.export_routing --all`, commit the graph
# and re-render the pages to turn it on
ROUTING_REGIONS = ["oxford"]
GRAPH_BASE = "routing/"


def _read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def _js_string(text: str) -> str:
    """A JavaScript string literal that is safe inside an inline <script>."""
    return json.dumps(text).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def config() -> dict:
    return {"regions": ROUTING_REGIONS, "base": GRAPH_BASE}


CSS = _read("panel.css")

_CORE = _read("routing.js") + "\n" + _read("directions.js")

JS = (
    f"const ROUTING_CORE_SRC = {_js_string(_CORE)};\n"
    + _read("panel.js")
    + """
return initRoutingPanel({map, L, ITEMS, PHONE, esc, store, VIEW, ICONS, RATINGS, RATECFG, CFG: """
    + json.dumps(config())
    + """,
  reportButton, reportShow, setSheet, setList});
"""
)
