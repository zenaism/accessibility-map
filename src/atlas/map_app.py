# ruff: noqa: E501
"""The map app (session B1): the search-first map, place card, details, route steps and Saved places, built on the
B0 foundation (src/atlas/ui_foundation.py). One self-contained HTML page: foundation CSS and JS, map.css and map.js,
and the data inside. Leaflet and its cluster plugin are vendored (atlas.leaflet, no request to another host); the basemap is USGS.

    from atlas.map_app import render
    html = render(data, title="Accessibility Map", nav="")

The chat assistant opens inside this page (a panel in the same window, no redirect): Ask fires atlas:open-ask and map.js opens
the embedded chat (atlas.assistant.page.embed). ask.html is only the fallback when scripts do not run. Reporting is the B2 form.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import leaflet, regions, report_form, routing_ui
from . import ui_foundation as ui
from .assistant import page as chat_page

WEB = Path(__file__).with_name("web") / "map"
REPORT_FALLBACK = "#report"  # the Report tab fires atlas:open-report; no GitHub link any more
ASK_FALLBACK = "ask.html"


def _json(obj) -> str:
    return (
        json.dumps(obj, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _hrefs() -> dict[str, str]:
    return {"saved": "#saved", "ask": ASK_FALLBACK, "report": REPORT_FALLBACK}


def _search() -> str:
    return (
        '<div class="topstack">'
        '<div class="search" role="search" aria-label="Search places">'
        + ui.icon("search")
        + '<input type="search" id="q" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="sug" '
        'placeholder="Search places" aria-label="Search places" autocomplete="off" enterkeyhint="search">'
        + ui.button("Clear search", "ghost", "close", icon_only=True, id="qclear", hidden=True)
        + ui.button("Filter by type", "ghost", "filter", icon_only=True, id="filter")
        + "</div>"
        '<div class="listbox" role="listbox" id="sug" aria-label="Suggestions" hidden></div>'
        '<div class="rowbtns" style="flex-wrap:nowrap">'
        + ui.button("Near me", "secondary", "near", id="near", style="flex:1")
        # phone: Near me and Ask (Saved places is in the tab bar). Desktop: Near me and Saved places side by side; Ask is in the top bar
        + '<span class="only-phone" style="display:contents">'
        + ui.button("Ask", "primary", "ask", href=ASK_FALLBACK, emit="atlas:open-ask", style="flex:1")
        + "</span>"
        '<span class="only-desktop" style="display:contents">'
        '<a class="btn btn-secondary" id="saved-open" href="#saved" data-go="saved" style="flex:1">'
        + ui.icon("save")
        + '<span>Saved places<span id="saved-count"></span></span></a></span>'
        "</div></div>"
    )


def _core() -> str:
    """The walking-route search (routing.js + directions.js), loaded into a Web Worker by the page."""
    return (
        (routing_ui.WEB / "routing.js").read_text(encoding="utf-8")
        + "\n"
        + (routing_ui.WEB / "directions.js").read_text(encoding="utf-8")
    )


def _map_js() -> str:
    body = (
        (WEB / "map.js")
        .read_text()
        .replace("/*__VOICE__*/", (WEB / "voice.js").read_text())
        .replace("/*__NAV__*/", (WEB / "nav.js").read_text())
        .replace("/*__REGION__*/", (WEB / "regionui.js").read_text())
    )
    return (WEB / "region.js").read_text() + "\n" + body


def _regions() -> list[dict]:
    """The visible cities for the switcher (atlas.regions.catalog), without the long layer lists."""
    return [{k: v for k, v in r.items() if k != "layers"} for r in regions.catalog()]


def _ratecfg() -> dict | None:
    from .map_viewer import ratings_config

    return ratings_config()


def _region_js() -> str:
    """window.atlasRegion(): the region the map is showing (the selected place, else the region nearest the map centre)."""
    return (
        "window.atlasRegion=function(){var A=window.AtlasMap,c=window.__MAPCFG;if(!A)return Object.keys(window.__MAPDATA)[0];"
        "if(A.S.region)return A.S.region;if(A.S.it&&A.S.it.p.region)return A.S.it.p.region;var m=A.map.getCenter(),best=null,bd=1e9;"
        "Object.keys(window.__MAPDATA).forEach(function(r){var v=c.view[r];if(!v)return;var d=Math.hypot((v[0][0]-m.lat)*111,(v[0][1]-m.lng)*85);if(d<bd){bd=d;best=r;}});"
        "return best||Object.keys(window.__MAPDATA)[0];};"
    )


CITY_BTN = (
    '<button type="button" class="btn btn-ghost {cls}" id="{id}" aria-haspopup="dialog" aria-expanded="false" aria-label="Choose a city">'
    '{pin}<span class="cn">Choose city</span>' + ui.icon("down") + "</button>"
)


def page_html(data: dict, title: str = "Accessibility Map", nav: str = "") -> str:
    cfg = {
        "view": {r["id"]: [r["center"], r["zoom"]] for r in regions.catalog()},
        "routing": routing_ui.config(),
        "title": title,
    }
    chat = chat_page.embed()
    top = ui.topbar("map", _hrefs(), settings=False)
    # the city switcher sits next to the product name on desktop
    top = top.replace(
        "</span><nav",
        "</span>" + CITY_BTN.format(id="city-btn-d", cls="city-btn", pin=ui.icon("pin")) + "<nav",
        1,
    )
    body = (
        '<a class="skip" href="#panel-body">Skip to the places</a>'
        '<header class="appbar phone-bar">'
        + ui.button("Back", "ghost", "back", icon_only=True, id="back", hidden=True)
        + '<h1 class="title" id="appbar-title">Accessibility Map</h1>'
        + CITY_BTN.format(id="city-btn", cls="city-btn", pin="")
        + ui.theme_toggle(id="theme-toggle")
        + "</header>"
        f'<div class="only-desktop">{top}<div class="city-pop" id="city-pop" role="region" aria-label="Cities" hidden></div></div>'
        '<main class="main"><h1 class="vh only-desktop">Accessibility Map</h1>'
        '<div class="leftcol">'
        + _search()
        + '<section class="panel" id="panel" aria-label="Places"><div class="grab"></div><div class="panel-body" id="panel-body" tabindex="-1"></div></section>'
        + "</div>"
        '<div class="mapwrap" role="region" aria-label="Map. A visual companion: every place on the map is also in the list.">'
        '<div id="map"></div>'
        '<button type="button" class="btn btn-secondary only-desktop lc-toggle" id="lc-toggle" aria-expanded="true" aria-controls="panel" aria-label="Hide places" data-label="Hide places">'
        + ui.icon("back")
        + "</button>"
        '<button type="button" class="btn btn-secondary legend-btn" id="legend-open">'
        + ui.icon("info")
        + "<span>Legend</span></button>"
        '<p class="hintpill" id="hint">Map is empty. Search or pick a type.</p>'
        '<div class="regionpill" id="region-pill" role="status" aria-live="polite" hidden></div>'
        '<div class="zoom"><button type="button" class="btn btn-icon btn-secondary" id="zin" aria-label="Zoom in">+</button>'
        '<button type="button" class="btn btn-icon btn-secondary" id="zout" aria-label="Zoom out">\u2212</button>'
        + ui.button("Show my location", "secondary", "near", icon_only=True, id="locate")
        + "</div>"
        '<span class="credit">USGS The National Map</span></div>' + chat["html"] + "</main>"
        f'<div class="only-phone">{ui.tabbar("map", _hrefs())}</div>'
        '<p class="vh" id="live" role="status" aria-live="polite"></p><span id="asof" hidden></span>'
    )
    full_title = "Accessibility Map"   # one tab name on every page; the city shows in the page itself (D-106)
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        "<title>" + full_title + "</title>"
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '<meta name="description" content="Wheelchair accessibility of places, restrooms, trails and events, with sources.">\n'
        + ui.head_snippet()
        + "\n"
        + leaflet.head()
        + f"<style>\n{ui.css()}\n{(WEB / 'map.css').read_text()}\n{chat['css']}\n{report_form.css()}\n</style></head>"
        f'<body class="ax mapapp">{ui.body_snippet()}\n{body}\n'
        f"<script>{ui.js()}</script>\n"
        f"<script>window.__MAPCFG={_json(cfg)};window.__MAPDATA={_json(data)};window.__REGIONS={_json(_regions())};</script>\n"
        f"<script>window.__ROUTECORE={_json(_core())};</script>\n"
        f"<script>{chat['js']}</script>\n"
        f"<script>{_map_js()}\n"
        "</script>\n"
        # B2 hook: the Rate or report form (settings, the region the map shows, the form itself)
        f"<script>{report_form.config_js(_ratecfg())}\n{_region_js()}\n{report_form.js()}\n</script>\n<script>"
        "</script>"
        "</body></html>"
    )


def render(data: dict, title: str = "Accessibility Map", nav: str = "", switch: str = "") -> str:
    """Same arguments as the old map_viewer.render (nav and switch are not used: the city switcher is B4)."""
    return page_html(data, title, nav)
