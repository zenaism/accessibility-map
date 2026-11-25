"""The map library, served from this repository (src/atlas/web/vendor/leaflet/), never from another host.

    from atlas.leaflet import head
    html = ... + head() + ...      # one <style> and two <script> blocks, inline

Leaflet 1.9.4 (BSD 2-Clause) and Leaflet.markercluster 1.5.3 (MIT): see the README in that folder.
"""

from __future__ import annotations

from pathlib import Path

VENDOR = Path(__file__).with_name("web") / "vendor" / "leaflet"
VERSIONS = {"leaflet": "1.9.4", "markercluster": "1.5.3"}


def _read(name: str) -> str:
    return (VENDOR / name).read_text(encoding="utf-8")


def head() -> str:
    """Leaflet and the cluster plugin as inline tags for <head>; they run before the page's own scripts."""
    css = _read("leaflet.css") + "\n" + _read("MarkerCluster.css")
    js = _read("leaflet.js") + "\n" + _read("leaflet.markercluster.js")
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>\n"
