"""Save screenshots of every Directions state (desktop 1280x800, phone 390x844) to docs/work_logs/screens/routing/.

    scripts/serve_routing.sh &            # serves data/map on http://localhost:8001
    PYTHONPATH=src python scripts/routing_screenshots.py [--base http://localhost:8001]
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "work_logs" / "screens" / "routing"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)
VIEWS = {"desktop": {"width": 1280, "height": 800}, "phone": {"width": 390, "height": 844}}


def link_ids():
    out = {}
    for region in ("oxford", "cincinnati"):
        for f in json.loads((ROOT / "data" / "map" / f"{region}_atlas.geojson").read_text())["features"]:
            out[f["properties"]["name"]] = f["properties"]["link_id"]
    return out


IDS = link_ids()


def pick(page, field, text):
    page.fill(f"#dp-{field}", text)
    page.wait_for_selector(f"#dp-{field}-list [role=option]")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")


def settle(page, state):
    page.wait_for_selector(f"#dirp[data-state={state}]", timeout=10000)
    page.wait_for_timeout(500)


def run(base):
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for view, size in VIEWS.items():
            phone = view == "phone"
            ctx = browser.new_context(viewport=size, has_touch=phone, is_mobile=phone)
            page = ctx.new_page()
            page.route("**/basemap.nationalmap.gov/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG))
            held = []

            def shot(name, view=view, page=page):
                page.screenshot(path=str(OUT / f"{view}-{name}.png"))

            def fresh(path="/oxford.html", page=page):
                page.goto(base + path)
                page.wait_for_selector("#list .card", state="attached")

            def reopen(to, frm=None, page=page, **kw):
                page.evaluate("AtlasRouting.close()")
                args = {"toPlaceId": IDS[to], **({"fromLatLng": frm} if frm else {}), **kw}
                page.evaluate(f"AtlasRouting.open({json.dumps(args)})")

            # empty panel
            fresh()
            page.click("#dir-open")
            page.wait_for_timeout(300)
            shot("01-empty")
            # a place card with "Route here"
            page.click("#dirp #dp-back")
            if phone:
                page.click("#sheet")
            page.wait_for_timeout(300)
            shot("02-card-route-here")
            # location asked, then denied (headless Chromium has no permission)
            page.locator("#list .dp-route-btn").first.click()
            page.wait_for_selector("#dirp[data-state=locate-ask]")
            shot("03-location-asked")
            page.click("#dp-ask-yes")
            settle(page, "locate-denied")
            shot("04-location-denied")
            # route found
            pick(page, "from", "Hodge Hall")
            pick(page, "to", "Western Dining")
            settle(page, "route")
            shot("05-route-found")
            if phone:
                page.click("#dp-toggle-steps")
                shot("06-steps")
                page.click("#dp-expand")
                shot("06b-full-list")
                page.click("#dp-expand")
            page.locator(".dp-step").nth(1).click()
            page.wait_for_timeout(400)
            shot("07-step-selected")
            # blind profile
            if phone:
                page.click("#dp-change")
            page.locator("#dirp .dp-radio").nth(1).click()
            settle(page, "route")
            shot("08-blind-profile")
            # a longer route with crossings and cautions
            if phone:
                page.click("#dp-change")
            page.click("[data-clear=to]")  # editing one end re-routes at once, so clear the other first
            pick(page, "from", "Bello Wood Fired")
            pick(page, "to", "Peffer Park")
            settle(page, "route")
            shot("09-route-with-warnings")
            # too far from a mapped path (a point in the fields north of town)
            reopen("Western Dining Commons", [39.5285, -84.7000])
            settle(page, "too-far")
            shot("10-too-far")
            # no step-free route (stairs-only pair from the golden file)
            reopen("Ambassador's Pointe Church", [39.5057, -84.7363])
            page.wait_for_timeout(1500)
            shot("11-no-route-or-other")
            # same start and end
            reopen("Hodge Hall", [39.5, -84.7])
            pick(page, "from", "Hodge Hall")
            settle(page, "same")
            shot("12-same-place")
            # loading (hold the graph request), then load failure
            ctx2 = browser.new_context(viewport=size, has_touch=phone, is_mobile=phone)
            p2 = ctx2.new_page()
            p2.route("**/basemap.nationalmap.gov/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG))
            p2.route("**/routing/oxford.graph.json", lambda r: held.append(r))
            p2.goto(base + "/oxford.html")
            p2.wait_for_selector("#list .card", state="attached")
            p2.evaluate(f"AtlasRouting.open({json.dumps({'toPlaceId': IDS['Western Dining Commons'], 'fromLatLng': [39.5079, -84.7368]})})")
            p2.wait_for_selector("#dirp[data-state=loading]")
            p2.screenshot(path=str(OUT / f"{view}-13-loading.png"))
            held[0].fulfill(status=500, body="nope")
            p2.wait_for_selector("#dirp[data-state=load-error]")
            p2.screenshot(path=str(OUT / f"{view}-14-load-error.png"))
            ctx2.close()
            # a different city (index page holds both) and a city without routing
            fresh("/cincinnati.html")
            assert page.locator("#dir-open").count() == 0
            ctx.close()
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8001")
    run(ap.parse_args().base)
