# ruff: noqa: E501
"""Measure the in-browser router (plan section 4.7): panel open time, graph size, parse/build time,
first route and repeat search time, with and without 4x CPU throttling.

    scripts/serve_routing.sh &       # port 8001
    PYTHONPATH=src python scripts/measure_routing.py [--region oxford] [--base http://localhost:8001]
"""

import argparse
import gzip
import json
import statistics
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)
WAIT = """async (args) => {
  const t0 = performance.now();
  AtlasRouting.open(args);
  const root = document.getElementById('dirp');
  await new Promise(res => {
    const done = () => ['route','too-far','no-route','load-error'].includes(root.dataset.state);
    if (done()) return res();
    new MutationObserver((_, o) => { if (done()) { o.disconnect(); res(); } }).observe(root, {attributes: true, attributeFilter: ['data-state']});
  });
  return performance.now() - t0;
}"""


def run(base, region):
    graph = ROOT / "data" / "map" / "routing" / f"{region}.graph.json"
    raw = graph.read_bytes()
    out = {"region": region, "raw_mb": len(raw) / 1e6, "gzip_mb": len(gzip.compress(raw, 6)) / 1e6}
    golden = json.loads((ROOT / "tests" / f"golden_routes_{region}.json").read_text()) if region == "oxford" else None
    feats = {f["properties"]["name"]: f["properties"]["link_id"] for f in json.loads((ROOT / "data" / "map" / f"{region}_atlas.geojson").read_text())["features"]}
    cases = {}
    if not golden:  # other regions: pick place pairs about 0.4 km and about 5 km apart (the first that route)
        import math

        pts = [
            (f["properties"]["name"], f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0])
            for f in json.loads((ROOT / "data" / "map" / f"{region}_atlas.geojson").read_text())["features"]
            if f["geometry"]["type"] == "Point"
        ]

        def km(a, b):
            return math.hypot((a[1] - b[1]) * 111, (a[2] - b[2]) * 111 * math.cos(math.radians(a[1])))

        for name, lo, hi in (("short", 0.3, 0.6), ("long", 4, 7)):
            cands = [(a, b) for a in pts for b in pts if lo < km(a, b) < hi][:40:5]
            cases[name] = [(None, b[0], [a[1], a[2]]) for a, b in cands]
    if golden:
        g = next(p for p in golden["pairs"] if p["label"] == "Hodge Hall -> Western Dining Commons")
        cases["short"] = (None, "Western Dining Commons", g["from"])
        g = next(p for p in golden["pairs"] if p["label"] == "Walter L. Gross Center -> Yum Cha")
        cases["long"] = (None, "Yum Cha", g["from"])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # CPU throttling applies to the page's main thread only, not to Web Workers; "main_thread" has no
        # Worker, so the same code runs on the (throttled) main thread: the worst case for a slow phone.
        for label, rate, workers in (("laptop_worker", 1, True), ("cpu_x4_worker", 4, True), ("cpu_x4_main_thread", 4, False)):
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            if not workers:
                ctx.add_init_script("window.Worker = undefined")
            page = ctx.new_page()
            page.route("**/basemap.nationalmap.gov/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG))
            page.goto(f"{base}/{region}.html")
            page.wait_for_selector("#list .card", state="attached")
            cdp = ctx.new_cdp_session(page)
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": rate})
            r = {}
            r["panel_open_ms"] = page.evaluate("() => { const t = performance.now(); document.getElementById('dir-open').click(); return performance.now() - t; }")
            page.evaluate("AtlasRouting.close()")
            for name, spec in cases.items():
                tries = spec if isinstance(spec, list) else [spec]
                for _, to, frm in tries:
                    args = {"toPlaceId": feats[to], "fromLatLng": frm}
                    cold = page.evaluate(WAIT, args)  # first call also downloads and parses the graph
                    if page.evaluate("AtlasRouting.state") == "route":
                        break
                else:
                    r[f"{name}_note"] = "no candidate pair routed"
                if name == "short":
                    st = page.evaluate("AtlasRouting.stats")
                    r.update(first_route_incl_download_ms=cold, download_parse_ms=st["loadMs"], graph_build_ms=st["buildMs"], nodes=st["nodes"], edges=st["edges"])
                times = []
                for _ in range(15):
                    page.evaluate("AtlasRouting.close()")
                    page.evaluate(WAIT, args)
                    times.append(page.evaluate("AtlasRouting.stats.searchMs"))
                r[f"search_{name}_ms_median"] = statistics.median(times)
                r[f"search_{name}_ms_max"] = max(times)
                r[f"result_{name}_feet"] = page.evaluate("AtlasRouting.result && AtlasRouting.result.length_feet")
            out[label] = r
            ctx.close()
        browser.close()
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="oxford")
    ap.add_argument("--base", default="http://localhost:8001")
    a = ap.parse_args()
    run(a.base, a.region)
