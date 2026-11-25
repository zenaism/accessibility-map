"""Leaflet is served from this repository: files and licences are there, no code comes from another host."""

import functools
import hashlib
import http.server
import re
import threading

import pytest

from atlas import leaflet, map_app, map_viewer

EMPTY = {"oxford": {"generated": "x", "features": []}}


def test_the_vendored_files_and_licences_are_present():
    names = {p.name for p in leaflet.VENDOR.iterdir()}
    need = {"leaflet.js", "leaflet.css", "leaflet.markercluster.js", "MarkerCluster.css"}
    assert need | {"LICENSE-leaflet.txt", "LICENSE-markercluster.txt", "README.md"} <= names
    assert "BSD 2-Clause" in (leaflet.VENDOR / "LICENSE-leaflet.txt").read_text()
    assert "Permission is hereby granted" in (leaflet.VENDOR / "LICENSE-markercluster.txt").read_text()
    assert "Leaflet 1.9.4" in (leaflet.VENDOR / "leaflet.js").read_text()[:200]
    sha = hashlib.sha256((leaflet.VENDOR / "leaflet.js").read_bytes()).hexdigest()
    assert sha.startswith("db49d009c841f5ca34a8")  # the 1.9.4 release file, unchanged


@pytest.mark.parametrize("html", [map_app.render(EMPTY), map_viewer.render(EMPTY, legacy=True)])
def test_pages_carry_leaflet_inline_and_name_no_other_host_for_code(html):
    assert "unpkg" not in html and "markerClusterGroup" in html
    for tag in re.findall(r"<(?:script|link)[^>]+>", html):
        assert not re.search(r"(src|href)=\"https?://", tag), tag


def test_the_map_loads_and_shows_markers_with_no_request_to_the_library_host(tmp_path):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    from .test_map_app import PNG, _data

    (tmp_path / "oxford.html").write_text(map_app.render(_data(), "Oxford"))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 375, "height": 812})
        ctx.add_init_script("localStorage.setItem('atlas-region','oxford')")
        pg = ctx.new_page()
        hosts = set()
        pg.on("request", lambda r: hosts.add(r.url.split("/")[2]))
        pg.route(
            "**/basemap.nationalmap.gov/**",
            lambda r: r.fulfill(status=200, content_type="image/png", body=PNG),
        )
        pg.goto(f"http://127.0.0.1:{port}/oxford.html")
        pg.wait_for_selector("html[data-map-ready]")
        pg.fill("#q", "library")
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#rows")
        assert pg.locator(".leaflet-container").count() == 1
        assert pg.evaluate("typeof L.markerClusterGroup") == "function"
        assert hosts <= {f"127.0.0.1:{port}", "basemap.nationalmap.gov"}, hosts
        b.close()
    srv.shutdown()
