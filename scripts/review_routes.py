# ruff: noqa: E501
"""R9 review: ten real Oxford routes through the page in headless Chromium, each compared with Python routing.route().

    scripts/serve_routing.sh &        # port 8001
    PYTHONPATH=src python scripts/review_routes.py
Prints one line per route and flags routes that look odd (likely missing OpenStreetMap data, not code bugs).
"""

import json
import math
from pathlib import Path

from playwright.sync_api import sync_playwright

from atlas import routing

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [
    ("King Library", "Armstrong Student Center"),
    ("Hall Auditorium", "Oxford Doughnut Shoppe"),
    ("Western Dining Commons", "Farmer School of Business"),
    ("Martin Dining Hall", "Yager Stadium"),
    ("Hodge Hall", "Kofenya"),
    ("McGuffey House and Museum", "Richard and Carole Cocks Art Museum"),
    ("Recreational Sports Center", "King Library"),
    ("Center for the Performing Arts", "Peffer Park"),
    ("Oxford Lane Library", "Graeter's Ice Cream"),
    ("Tappan Hall", "Shriver Center"),
]
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


def main(base="http://localhost:8001"):
    ids = {
        f["properties"]["name"]: f["properties"]["link_id"]
        for f in json.loads((ROOT / "data/map/oxford_atlas.geojson").read_text())["features"]
    }
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1280, "height": 800})
        page.route(
            "**/basemap.nationalmap.gov/**",
            lambda r: r.fulfill(status=200, content_type="image/png", body=PNG),
        )
        page.goto(base + "/oxford.html")
        page.wait_for_selector("#list .card", state="attached")
        for a, z in PAIRS:
            for profile in ("wheelchair", "blind"):
                page.goto(f"{base}/oxford.html#route={ids[a]},{ids[z]}&profile={profile}")
                page.wait_for_function("['route','no-route','too-far','same'].includes(AtlasRouting.state)")
                st = page.evaluate("AtlasRouting.state")
                if st != "route":
                    rows.append((a, z, profile, st, "", [], False))
                    continue
                res, pts = page.evaluate("[AtlasRouting.result, AtlasRouting.points]")
                py = routing.route(
                    "oxford", pts["from"][0], pts["from"][1], pts["to"][0], pts["to"][1], profile
                )
                same = (
                    py is not None
                    and py["directions"] == res["directions"]
                    and py["length_feet"] == res["length_feet"]
                    and py["compared_with_shortest"] == res["compared_with_shortest"]
                )
                straight = math.hypot(
                    (pts["from"][0] - pts["to"][0]) * 364000,
                    (pts["from"][1] - pts["to"][1]) * 364000 * math.cos(math.radians(39.5)),
                )
                flags = []
                if res["length_feet"] > 1.7 * straight and res["length_feet"] > 600:
                    flags.append(f"long detour ({res['length_feet'] / straight:.1f}x straight line)")
                if res["road_without_sidewalk_feet"] > 150:
                    flags.append(f"{res['road_without_sidewalk_feet']} ft on road with no sidewalk mapped")
                if res["steep_sections"] > 2:
                    flags.append(f"{res['steep_sections']} steep sections")
                if res["crossings"]["unmarked_or_unknown"]:
                    flags.append(f"{res['crossings']['unmarked_or_unknown']} unmarked/unknown crossings")
                rows.append(
                    (
                        a,
                        z,
                        profile,
                        st,
                        f"{res['length_feet']} ft, {len(res['directions'])} steps, {res['crossings']['total']} crossings",
                        flags,
                        same,
                    )
                )
        b.close()
    ok = all(r[6] for r in rows if r[3] == "route")
    for a, z, prof, st, summ, flags, same in rows:
        print(
            f"{a} -> {z} [{prof}] {st} {summ} | python {'MATCH' if same else 'DIFFERENT' if st == 'route' else '-'} | {'; '.join(flags) or 'nothing odd'}"
        )
    print("ALL MATCH PYTHON" if ok else "MISMATCH")


if __name__ == "__main__":
    main()
