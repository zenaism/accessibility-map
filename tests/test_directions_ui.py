# ruff: noqa: E501  (long inline JavaScript strings)
"""The Directions panel in a real browser (Chromium via Playwright) on the Oxford map.

Pages are rendered from the template into a temporary site together with the exported graph, served over
HTTP (fetching the graph from file:// fails). Leaflet comes from unpkg: it is downloaded once and served from
a local copy; the map tiles are replaced by a blank image. Tests are skipped when the graph cannot be built,
when Leaflet cannot be fetched, or when Chromium is missing. No fixed sleeps: every wait is for a state.

axe-core accessibility checks run when `npm install axe-core@4.10.2 --no-save --prefix ./.axe` has been done.
"""

import functools
import http.server
import json
import re
import shutil
import threading
from pathlib import Path

import pytest

from atlas import export_routing, routing, routing_ui
from atlas.core import ROOT
from atlas.map_viewer import render

from .mapdata import page_data

playwright_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_api.sync_playwright

pytestmark = pytest.mark.skipif(
    not (routing.PROCESSED / "oxford" / "walk_edges.parquet").exists(),
    reason="walking network not downloaded",
)

GOLDEN = json.loads((Path(__file__).parent / "golden_routes_oxford.json").read_text())
AXE = ROOT / ".axe" / "node_modules" / "axe-core" / "axe.min.js"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)
CDN = [
    "leaflet@1.9.4/dist/leaflet.css",
    "leaflet@1.9.4/dist/leaflet.js",
    "leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
    "leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
]
PLACES = {}  # name -> link_id, filled by the site fixture
FIRST_CINCINNATI = {}


def _page_data(name: str):
    old = (ROOT / "data" / "map" / f"{name}.html").read_text()
    title = re.search(r"<title>(.*?) · Accessibility Map</title>", old).group(1)
    found = re.search(r'<span id="asof"></span>(.*?)</p></div>', old, re.S)
    return page_data(old), title, found.group(1) if found else ""


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    for name in ("oxford", "index"):
        data, title, nav = _page_data(name)
        (root / f"{name}.html").write_text(render(data, title, nav, legacy=True))
        for region, fc in data.items():
            for f in fc["features"]:
                PLACES[f["properties"]["name"]] = f["properties"]["link_id"]
                if region == "cincinnati":
                    FIRST_CINCINNATI.setdefault("id", f["properties"]["link_id"])
                    FIRST_CINCINNATI.setdefault(
                        "pt", [f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]]
                    )
    # pages with an explicit list of regions that have the panel (whatever ROUTING_REGIONS is today)
    from atlas import map_viewer

    data, title, nav = _page_data("index")
    marker = json.dumps(routing_ui.config())
    assert marker in map_viewer.ROUTING_JS
    saved = map_viewer.ROUTING_JS
    try:
        for name, regions in (("oxford_only", ["oxford"]), ("both_cities", ["oxford", "cincinnati"])):
            map_viewer.ROUTING_JS = saved.replace(
                marker, json.dumps({**routing_ui.config(), "regions": regions})
            )
            (root / f"{name}.html").write_text(render(data, title, nav, legacy=True))
    finally:
        map_viewer.ROUTING_JS = saved
    graph = ROOT / "data" / "map" / "routing" / "oxford.graph.json"
    if not graph.exists():
        export_routing.write("oxford")
    (root / "routing").mkdir()
    shutil.copy(graph, root / "routing" / "oxford.graph.json")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

    handler = functools.partial(Quiet, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="session")
def cdn():
    """Leaflet is vendored in the page now (atlas.leaflet): nothing is downloaded. Kept so tests keep their signature."""
    return {}


@pytest.fixture(scope="module")  # module scope: other test files start their own Playwright in the same run
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium not available ({e})")
        yield b
        b.close()


def _new_page(browser, cdn, **ctx_args):
    ctx = browser.new_context(**ctx_args)
    page = ctx.new_page()

    def unpkg(route):
        url = route.request.url.split("unpkg.com/", 1)[1]
        f = cdn.get(url)
        if f is None:
            return route.fulfill(status=404, body="")
        ctype = "text/css" if url.endswith(".css") else "text/javascript"
        route.fulfill(status=200, content_type=ctype, body=f.read_bytes())

    page.route("https://unpkg.com/**", unpkg)
    page.route(
        "**/basemap.nationalmap.gov/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG)
    )
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on(
        "console",
        lambda m: (
            page.errors.append(m.text)
            if m.type == "error" and "Failed to load resource" not in m.text
            else None
        ),
    )
    return page


@pytest.fixture
def page(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 1280, "height": 800})
    p.goto(f"{site}/oxford.html")
    p.wait_for_selector("#list .card", state="attached")
    yield p
    assert p.errors == [], p.errors
    p.context.close()


@pytest.fixture
def phone(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    p.goto(f"{site}/oxford.html")
    p.wait_for_selector("#list .card", state="attached")
    yield p
    assert p.errors == [], p.errors
    p.context.close()


def choose(page, field, text):
    page.fill(f"#dp-{field}", text)
    page.wait_for_selector(f"#dp-{field}-list [role=option]")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")


def state(page):
    return page.get_attribute("#dirp", "data-state")


def wait_state(page, st):
    page.wait_for_selector(f"#dirp[data-state={st}]", timeout=15000)


def route_hash(a, b, profile="wheelchair"):
    return f"#route=@{a[0]};{a[1]},@{b[0]};{b[1]}&profile={profile}"


def golden(label):
    return next(p for p in GOLDEN["pairs"] if p["label"] == label)


def axe_check(page, where="#dirp"):
    if not AXE.exists():
        pytest.skip("axe-core not installed (npm install axe-core@4.10.2 --no-save --prefix ./.axe)")
    page.add_script_tag(content=AXE.read_text())
    res = page.evaluate(
        """async (where) => (await axe.run(document.querySelector(where),
            {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']}})).violations
            .map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target.join(' ') + ' :: ' + n.html.slice(0, 120))}))""",
        where,
    )
    assert res == [], json.dumps(res, indent=1)


# ------------------------------------------------------------------------------------------ routes
def test_route_found_between_two_places(page):
    page.click("#dir-open")
    page.wait_for_selector("#dirp:not([hidden])")
    assert state(page) == "empty"
    choose(page, "from", "Hodge Hall")
    choose(page, "to", "Western Dining")
    wait_state(page, "route")
    assert page.locator(".dp-step").count() >= 2
    assert page.locator("path.dp-line").count() == 1 and page.locator("path.dp-casing").count() == 1
    assert page.locator(".dp-pin.start").count() == 1 and page.locator(".dp-pin.end").count() == 1
    assert "No stairs" in page.inner_text("#dp-facts")
    assert "not checked on site" in page.inner_text("#dp-note")
    assert "estimate" in page.inner_text("#dp-note")
    assert page.evaluate("document.activeElement.id") == "dp-sum-h"  # focus moves to the summary
    assert page.evaluate("AtlasRouting.isReady()")
    # Python-style sentences, one per step, ending in a full stop
    assert all(d.endswith(".") for d in page.evaluate("AtlasRouting.result.directions"))


def test_selected_step_is_highlighted_and_next_previous_work(page):
    page.goto(
        page.url.split("#")[0]
        + route_hash(*[golden("Walter L. Gross Center -> Yum Cha")[k] for k in ("from", "to")])
    )
    wait_state(page, "route")
    n = page.locator(".dp-step").count()
    page.locator(".dp-step").nth(1).click()
    assert page.get_attribute(".dp-step[data-i='1']", "aria-current") == "step"
    assert page.inner_text("#dp-stepof") == f"Step 2 of {n + 1}"
    page.click("#dp-next")
    assert page.get_attribute(".dp-step[data-i='2']", "aria-current") == "step"
    page.click("#dp-prev")
    page.click("#dp-prev")
    assert page.get_attribute(".dp-step[data-i='0']", "aria-current") == "step"
    assert page.is_disabled("#dp-prev")
    assert page.evaluate("document.querySelectorAll('path.dp-hl')[0].getAttribute('d')") not in (
        None,
        "",
        "M0 0",
    )


@pytest.mark.parametrize("profile", ["wheelchair", "blind"])
@pytest.mark.parametrize(
    "label",
    [
        p["label"]
        for p in GOLDEN["pairs"]
        if p["category"] in ("avoids stairs", "many crossings", "blind route differs")
    ][:5],
)
def test_ui_shows_the_python_directions(page, label, profile):
    """The page, from the link, gives the same sentences as Python routing.route() (golden file)."""
    g = golden(label)
    want = g["results"][profile]["result"]
    page.goto(page.url.split("#")[0] + route_hash(g["from"], g["to"], profile))
    wait_state(page, "route")
    got = page.evaluate("AtlasRouting.result")
    assert got["directions"] == want["directions"]
    assert got["length_feet"] == want["length_feet"]
    assert got["compared_with_shortest"] == want["compared_with_shortest"]
    assert page.inner_text("#dp-compare") == want["compared_with_shortest"]
    assert want["crossings_text"] in page.inner_text("#dp-facts")
    shown = page.locator(".dp-step .dp-st").all_inner_texts()
    for d, text in zip(want["directions"], shown, strict=False):
        assert d in text


def test_profile_choice_changes_the_route_and_is_remembered(page):
    g = golden("Kofenya -> Garland Hall")
    page.goto(page.url.split("#")[0] + route_hash(g["from"], g["to"]))
    wait_state(page, "route")
    first = page.evaluate("AtlasRouting.result.directions.join('|')")
    page.locator("#dirp .dp-radio").nth(1).click()
    page.wait_for_function(
        "AtlasRouting.result && AtlasRouting.result.profile === 'blind' && AtlasRouting.state === 'route'"
    )
    assert page.evaluate("AtlasRouting.result.directions.join('|')") != first
    assert page.evaluate("localStorage.getItem('atlas-route-profile')") == "blind"
    assert page.evaluate("document.querySelector('input[name=dp-profile]:checked').value") == "blind"


def test_route_here_on_a_card_prefills_the_destination(page):
    page.locator("#list .dp-route-btn").first.click()
    wait_state(page, "locate-ask")
    to = page.input_value("#dp-to")
    assert to and to == page.locator("#list .card h3").first.inner_text()
    assert page.input_value("#dp-from") == "My location"
    # the old Google Maps link is still there, as the second choice, inside Details
    page.click("#dp-back")
    page.locator("#list [data-a=det]").first.click()
    assert page.locator("#list .dp-gmaps").count() == 1


def test_assistant_hook_event_and_api(page):
    assert page.evaluate("typeof AtlasRouting.open") == "function"
    pid = PLACES["Western Dining Commons"]
    page.evaluate(
        "pid => window.dispatchEvent(new CustomEvent('atlas:route-to', {detail: {placeId: pid, profile: 'blind'}}))",
        pid,
    )
    wait_state(page, "locate-ask")
    assert page.input_value("#dp-to") == "Western Dining Commons"
    assert page.evaluate("document.querySelector('input[name=dp-profile]:checked').value") == "blind"
    page.evaluate("AtlasRouting.close()")
    page.evaluate("pid => AtlasRouting.open({toPlaceId: pid, fromLatLng: [39.5079, -84.7368]})", pid)
    wait_state(page, "route")


def test_copy_link_round_trip(page, site):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.click("#dir-open")
    choose(page, "from", "Hodge Hall")
    choose(page, "to", "Western Dining")
    wait_state(page, "route")
    n = page.evaluate("AtlasRouting.result.length_feet")
    page.click("#dp-copy-link")
    link = page.evaluate("navigator.clipboard.readText()")
    assert "#route=" in link and "profile=" in link
    page.goto(link)
    wait_state(page, "route")
    assert page.evaluate("AtlasRouting.result.length_feet") == n
    page.click("#dp-copy-text")
    text = page.evaluate("navigator.clipboard.readText()")
    assert (
        text.startswith("Directions from Hodge Hall to Western Dining Commons")
        and "not checked on site" in text
    )
    assert page.get_attribute("#dp-google", "href").startswith("https://www.google.com/maps/dir/?api=1")


# ------------------------------------------------------------------------------------------ states
def test_state_empty_and_help(page):
    page.click("#dir-open")
    assert state(page) == "empty"
    assert "Choose where you are starting" in page.inner_text("#dp-empty")
    assert page.evaluate("document.activeElement.id") == "dp-from"


def test_state_loading_then_route(page, site):
    held = []
    page.route("**/routing/oxford.graph.json", lambda r: held.append(r))
    pid = PLACES["Western Dining Commons"]
    page.evaluate("pid => AtlasRouting.open({toPlaceId: pid, fromLatLng: [39.5079, -84.7368]})", pid)
    wait_state(page, "loading")
    assert "Loading walking map" in page.inner_text("#dp-status")
    page.fill("#dp-from", "Hod")  # fields stay usable while loading
    assert page.input_value("#dp-from") == "Hod"
    page.unroute("**/routing/oxford.graph.json")
    held[0].continue_()
    page.fill("#dp-from", "")
    choose(page, "from", "Hodge Hall")
    wait_state(page, "route")


def test_state_load_error_and_retry(page):
    page.route("**/routing/oxford.graph.json", lambda r: r.fulfill(status=500, body="no"))
    pid = PLACES["Western Dining Commons"]
    page.evaluate("pid => AtlasRouting.open({toPlaceId: pid, fromLatLng: [39.5079, -84.7368]})", pid)
    wait_state(page, "load-error")
    assert "could not load the walking map" in page.inner_text("#dp-alert")
    assert page.locator("#dp-alert a[href*='google.com/maps']").count() == 1
    assert page.evaluate("document.activeElement.id") == "dp-retry"
    page.unroute("**/routing/oxford.graph.json")
    page.click("#dp-retry")
    wait_state(page, "route")


def test_state_location_asked_denied_and_granted(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 1280, "height": 800})
    p.goto(f"{site}/oxford.html")
    p.wait_for_selector("#list .card", state="attached")
    pid = PLACES["Western Dining Commons"]
    p.evaluate("pid => AtlasRouting.open({toPlaceId: pid})", pid)
    wait_state(p, "locate-ask")
    assert p.is_visible("#dp-ask") and "never sent to us" in p.inner_text("#dp-ask")
    p.click("#dp-ask-no")  # Not now keeps going
    assert state(p) == "empty" and p.evaluate("document.activeElement.id") == "dp-from"
    p.click("#dp-from")
    p.locator("#dp-from-list [role=option]", has_text="My location").click()
    wait_state(p, "locate-ask")
    p.context.set_geolocation(None)
    p.click("#dp-ask-yes")
    wait_state(p, "locate-denied")  # no permission granted: the browser refuses
    assert "could not find your location" in p.inner_text("#dp-alert")
    assert p.evaluate("document.activeElement.id") == "dp-from"
    p.context.grant_permissions(["geolocation"])
    p.context.set_geolocation({"latitude": 39.5079, "longitude": -84.7368})
    p.click("#dp-from")
    p.locator("#dp-from-list [role=option]", has_text="My location").click()
    wait_state(p, "route")  # permission already granted: no explanation box
    assert p.input_value("#dp-from") == "My location"
    assert p.errors == [], p.errors
    p.context.close()


def test_state_too_far_from_a_mapped_path(page):
    far = [39.5285, -84.7000]  # open fields, still in the Oxford area
    page.goto(page.url.split("#")[0] + route_hash(far, [39.5079, -84.7368]))
    wait_state(page, "too-far")
    assert "more than 500 feet from a mapped path" in page.inner_text("#dp-alert")
    assert "The start" in page.inner_text("#dp-alert")
    assert page.evaluate("document.activeElement.id") == "dp-from"


def test_state_no_step_free_route(page):
    g = next(p for p in GOLDEN["pairs"] if p["results"]["wheelchair"]["reason"] == "no_step_free_route")
    page.goto(page.url.split("#")[0] + route_hash(g["from"], g["to"]))
    wait_state(page, "no-route")
    assert "no step-free route" in page.inner_text("#dp-alert")
    assert page.locator("#dp-alert a[href*='google.com/maps']").count() == 1
    assert page.locator("#dp-alert [data-report-fallback], #dp-alert [data-report]").count() >= 1


def test_state_same_start_and_end(page):
    here = [39.5079, -84.7368]
    page.goto(page.url.split("#")[0] + route_hash(here, here))
    wait_state(page, "same")
    assert "You are already there." in page.inner_text("#dp-alert")


def test_state_unavailable_and_mixed_cities(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 1280, "height": 800})
    p.goto(f"{site}/oxford_only.html")
    p.wait_for_selector("#list .card", state="attached")
    cid = FIRST_CINCINNATI["id"]
    p.evaluate(
        "([id, pt]) => AtlasRouting.open({toPlaceId: id, fromLatLng: pt})",
        [cid, [FIRST_CINCINNATI["pt"][0] + 0.002, FIRST_CINCINNATI["pt"][1]]],
    )
    wait_state(p, "unavailable")
    assert "not available for this area yet" in p.inner_text("#dp-alert")
    p.goto(
        f"{site}/index.html"
    )  # both cities have a graph here: an Oxford start and a Cincinnati place do not mix
    p.wait_for_selector("#list .card", state="attached")
    p.evaluate("([id]) => AtlasRouting.open({toPlaceId: id, fromLatLng: [39.5079, -84.7368]})", [cid])
    wait_state(p, "mixed")
    assert "different cities" in p.inner_text("#dp-alert")
    p.context.close()


def test_state_end_without_mapped_door_shows_the_note(page):
    # Hall Auditorium has an accessible entrance mapped: no note. A place whose saved route ends at the
    # building point ("no accessible door is mapped") shows the note under the steps.
    page.evaluate(
        "pid => AtlasRouting.open({toPlaceId: pid, fromLatLng: [39.5079, -84.7368]})",
        PLACES["Hall Auditorium"],
    )
    wait_state(page, "route")
    assert page.is_hidden("#dp-doornote")
    no_door = next(
        f["properties"]
        for f in _page_data("oxford")[0]["oxford"]["features"]
        if "no accessible door is mapped"
        in " ".join(((f["properties"].get("getting_there") or {}).get("route") or {}).get("directions", []))
    )
    page.evaluate(
        "pid => AtlasRouting.open({toPlaceId: pid, fromLatLng: [39.5079, -84.7368]})", no_door["link_id"]
    )
    wait_state(page, "route")
    assert page.is_visible("#dp-doornote") and "no accessible door is mapped" in page.inner_text(
        "#dp-doornote"
    )


# ------------------------------------------------------------------------------------------ keyboard and focus
def test_keyboard_only_route_and_escape_returns_focus(page):
    page.focus("#dir-open")
    page.keyboard.press("Enter")
    page.wait_for_selector("#dirp:not([hidden])")
    assert page.evaluate("document.activeElement.id") == "dp-from"
    page.keyboard.type("Hodge")
    page.keyboard.press("ArrowDown")
    assert page.get_attribute("#dp-from", "aria-expanded") == "true"
    assert page.get_attribute("#dp-from", "aria-activedescendant")
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "dp-to"  # Enter moves on to the destination
    page.keyboard.type("Western Dining")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    wait_state(page, "route")
    assert page.evaluate("document.activeElement.id") == "dp-sum-h"
    page.keyboard.press("Tab")  # first step comes right after the summary and the previous/next buttons
    page.keyboard.press("Escape")
    page.wait_for_selector("#dirp", state="hidden")
    assert page.evaluate("document.activeElement.id") == "dir-open"


def test_escape_closes_the_suggestions_first(page):
    page.click("#dir-open")
    page.keyboard.type("Hod")
    assert page.get_attribute("#dp-from", "aria-expanded") == "true"
    page.keyboard.press("Escape")
    assert page.get_attribute("#dp-from", "aria-expanded") == "false"
    assert page.is_visible("#dirp")  # the panel itself stays open
    page.keyboard.press("Escape")
    page.wait_for_selector("#dirp", state="hidden")


def test_tab_order_follows_reading_order(page):
    g = golden("Minnich Hall -> McGuffey House and Museum")
    page.goto(page.url.split("#")[0] + route_hash(g["from"], g["to"]))
    wait_state(page, "route")
    order = page.evaluate(
        """() => [...document.querySelectorAll('#dirp button, #dirp a[href], #dirp input, #dirp [tabindex]')]
            .filter(e => !e.hidden && e.offsetParent !== null && e.tabIndex >= 0 && !e.closest('[hidden]'))
            .map(e => e.id || e.className.split(' ')[0] || e.tagName)"""
    )
    i = lambda x: order.index(x)  # noqa: E731
    assert i("dp-back") < i("dp-from") < i("dp-to") < i("dp-swap") or i("dp-from") < i("dp-swap") < i("dp-to")
    assert i("dp-to") < i("dp-profile") if "dp-profile" in order else True
    assert i("dp-to") < i("dp-prev") < i("dp-next") < i("dp-step") < i("dp-copy-text")


def test_targets_text_and_panel_size_on_desktop(page):
    page.click("#dir-open")
    choose(page, "from", "Hodge Hall")
    choose(page, "to", "Western Dining")
    wait_state(page, "route")
    small = page.evaluate(
        """() => [...document.querySelectorAll('#dirp button, #dirp .btn, #dirp input')].filter(e => e.offsetParent && !e.closest('[hidden]'))
            .map(e => [e.id || e.className, Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)])
            .filter(([n, w, h]) => !n.includes('dp-radio') && (h < 44 || w < 44))"""
    )
    assert small == [], small
    fonts = page.evaluate(
        """() => [...document.querySelectorAll('#dirp .dp-st, #dirp input, #dirp button, #dirp .dp-facts span')].filter(e => e.offsetParent)
            .map(e => parseFloat(getComputedStyle(e).fontSize)).filter(s => s < 16)"""
    )
    assert fonts == []


def test_panel_opens_fast(page):
    ms = page.evaluate(
        """() => { const b = document.getElementById('dir-open'); const t0 = performance.now(); b.click();
            const t = performance.now() - t0; return {t, visible: !document.getElementById('dirp').hidden}; }"""
    )
    assert ms["visible"] and ms["t"] < 100, ms


# ------------------------------------------------------------------------------------------ phone and narrow
def test_phone_bottom_sheet_heights(phone):
    phone.click("#dir-open")
    assert phone.is_visible("#dp-from")
    choose(phone, "from", "Hodge Hall")
    choose(phone, "to", "Western Dining")
    wait_state(phone, "route")
    assert phone.get_attribute("#dirp", "data-height") == "summary"  # map first
    assert phone.is_hidden("#dp-steps")
    assert phone.get_attribute("#dp-toggle-steps", "aria-expanded") == "false"
    phone.click("#dp-toggle-steps")
    assert phone.is_visible("#dp-steps") and phone.get_attribute("#dirp", "data-height") == "steps"
    phone.click("#dp-expand")
    assert phone.get_attribute("#dirp", "data-height") == "full"
    phone.click("#dp-change")
    assert phone.is_visible("#dp-from")
    # the route is still on the map and not hidden under the sheet
    box = phone.evaluate(
        "(() => { const r = document.querySelector('path.dp-line').getBoundingClientRect(); return [r.top, r.bottom]; })()"
    )
    sheet_top = phone.evaluate("document.getElementById('dirp').getBoundingClientRect().top")
    assert box[1] <= sheet_top + 2


@pytest.mark.parametrize("width", [320, 390])
def test_no_horizontal_scroll_on_narrow_screens(browser, cdn, site, width):
    p = _new_page(browser, cdn, viewport={"width": width, "height": 700}, is_mobile=True, has_touch=True)
    p.goto(f"{site}/oxford.html" + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(p, "route")
    p.click("#dp-toggle-steps")
    sizes = p.evaluate(
        "({page: document.documentElement.scrollWidth, panel: document.getElementById('dirp').scrollWidth, scroll: document.getElementById('dp-scroll').scrollWidth, scrollClient: document.getElementById('dp-scroll').clientWidth, w: innerWidth})"
    )
    assert sizes["page"] <= sizes["w"] and sizes["panel"] <= sizes["w"]
    assert sizes["scroll"] <= sizes["scrollClient"]
    p.click("#dp-change")
    assert p.evaluate("document.getElementById('dirp').scrollWidth") <= width
    assert p.errors == [], p.errors
    p.context.close()


def test_200_percent_zoom_equivalent(browser, cdn, site):
    # 200% zoom on a 1280 px window is a 640 px wide layout: the phone layout, no horizontal scroll
    p = _new_page(browser, cdn, viewport={"width": 640, "height": 400})
    p.goto(f"{site}/oxford.html" + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(p, "route")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert p.evaluate("document.getElementById('dirp').scrollWidth <= innerWidth")
    p.context.close()


def test_reduced_motion_and_forced_colours_still_work(browser, cdn, site):
    p = _new_page(
        browser, cdn, viewport={"width": 1280, "height": 800}, reduced_motion="reduce", forced_colors="active"
    )
    p.goto(f"{site}/oxford.html" + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(p, "route")
    assert p.locator("path.dp-line").count() == 1
    # the route line and its casing must not be the same colour, or the route would vanish
    colours = p.evaluate(
        "['dp-casing','dp-line'].map(c => getComputedStyle(document.querySelector('path.' + c)).stroke)"
    )
    assert colours[0] != colours[1], colours
    assert p.errors == [], p.errors
    p.context.close()


# ------------------------------------------------------------------------------------------ pick on map
def test_pick_on_map_and_escape_cancels(page):
    page.click("#dir-open")
    choose(page, "to", "Western Dining")
    page.click("#dp-from")
    page.locator("#dp-from-list [role=option]", has_text="Pick on map").click()
    wait_state(page, "picking")
    assert "Tap the map" in page.inner_text("#dp-pick-text")
    page.keyboard.press("Escape")
    assert state(page) != "picking"
    page.click("#dp-from")
    page.locator("#dp-from-list [role=option]", has_text="Pick on map").click()
    wait_state(page, "picking")
    # tap the map near Hodge Hall's start
    page.evaluate("document.getElementById('map')._leaflet_id")
    box = page.locator("#map").bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5)
    page.wait_for_function(
        "['route','too-far','no-route','load-error','loading','searching'].includes(AtlasRouting.state)"
    )
    assert page.input_value("#dp-from") == "Point on the map"


# ------------------------------------------------------------------------------------------ axe
@pytest.mark.parametrize(
    "name", ["empty", "route", "route-blind", "too-far", "no-route", "location-asked", "same"]
)
def test_axe_on_every_state_desktop(page, name):
    here = [39.5079, -84.7368]
    near = [39.5088, -84.7345]
    nr = next(p for p in GOLDEN["pairs"] if p["results"]["wheelchair"]["reason"] == "no_step_free_route")
    base = page.url.split("#")[0]
    if name == "empty":
        page.click("#dir-open")
    elif name == "location-asked":
        page.evaluate("pid => AtlasRouting.open({toPlaceId: pid})", PLACES["Western Dining Commons"])
        wait_state(page, "locate-ask")
    else:
        h = {
            "route": route_hash(here, near),
            "route-blind": route_hash(here, near, "blind"),
            "too-far": route_hash([39.5285, -84.7], near),
            "no-route": route_hash(nr["from"], nr["to"]),
            "same": route_hash(here, here),
        }[name]
        page.goto(base + h)
        wait_state(page, {"route-blind": "route"}.get(name, name))
    axe_check(page)


@pytest.mark.parametrize("view", ["summary", "steps", "form"])
def test_axe_on_phone_sheet(phone, view):
    phone.goto(phone.url.split("#")[0] + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(phone, "route")
    if view in ("steps", "form"):
        phone.click("#dp-toggle-steps")
    if view == "form":
        phone.click("#dp-change")
    axe_check(phone)


def test_axe_on_a_card_with_route_here(page):
    page.locator("#list [data-a=det]").first.click()
    axe_check(page, "#list")


# ------------------------------------------------------------------------------------------ loading and popups
def test_graph_is_not_downloaded_until_the_panel_is_used(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 1280, "height": 800})
    graph_requests = []
    p.on("request", lambda r: graph_requests.append(r.url) if r.url.endswith(".graph.json") else None)
    p.goto(f"{site}/oxford.html")
    p.wait_for_selector("#list .card", state="attached")
    assert graph_requests == []  # nothing yet
    p.hover("#dir-open")  # hovering the button starts the download (prefetch)
    p.wait_for_function("AtlasRouting.isReady()")
    assert len(graph_requests) == 1
    p.click("#dir-open")  # opening the panel does not download it again
    assert len(graph_requests) == 1
    p.context.close()


def test_route_here_in_the_map_popup(page):
    page.locator("#list [data-a=map]").first.click()
    page.wait_for_selector(".leaflet-popup .dp-route-btn")
    name = page.inner_text(".leaflet-popup h3")
    page.click(".leaflet-popup .dp-route-btn")
    wait_state(page, "locate-ask")
    assert page.input_value("#dp-to") == name


def test_short_wide_screen_phone_landscape_shows_the_route_first(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 844, "height": 390}, is_mobile=True, has_touch=True)
    p.goto(f"{site}/oxford.html" + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(p, "route")
    assert p.is_hidden("#dp-from") and p.is_visible("#dp-sum-h") and p.is_visible("#dp-change")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.click("#dp-change")
    assert p.is_visible("#dp-from")
    assert p.errors == [], p.errors
    p.context.close()


def test_chat_closes_when_it_sends_you_to_directions_on_a_phone(phone):
    phone.tap("#ask-open")
    phone.wait_for_selector("#ow-panel:not([hidden])")
    pid = PLACES["Western Dining Commons"]
    phone.evaluate(
        "pid => window.dispatchEvent(new CustomEvent('atlas:route-to', {detail: {placeId: pid}}))", pid
    )
    wait_state(phone, "locate-ask")
    assert phone.is_hidden("#ow-panel")
    top = phone.evaluate(
        "(() => { const r = document.getElementById('dirp').getBoundingClientRect(); return !!document.elementFromPoint(195, r.top + 40).closest('#dirp'); })()"
    )
    assert top  # the Directions sheet is what you see, not the chat


SPEECH_STUB = """
window.__said = []; window.__cancels = 0;
window.SpeechSynthesisUtterance = function (t) { this.text = t; };
Object.defineProperty(window, 'speechSynthesis', {configurable: true, value: { speak(u) { window.__said.push(u); }, cancel() { window.__cancels++; window.__said = []; }, pause() {}, resume() {} }});
"""


def test_read_aloud_speaks_the_route_and_can_be_stopped(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 1280, "height": 800})
    p.add_init_script(SPEECH_STUB)
    p.goto(f"{site}/oxford.html" + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(p, "route")
    steps = p.locator(".dp-step").count()
    assert p.is_visible("#dp-speak") and p.inner_text("#dp-speak").strip() == "Read aloud"
    p.click("#dp-speak")
    said = p.evaluate("__said.map(u => u.text)")
    assert len(said) == steps + 2  # summary, every step, arrival
    assert said[0].startswith("Route from") and "No stairs" in said[0]
    assert said[1].startswith("Step 1.") and said[-1].startswith("You have arrived")
    assert "not checked on site" in said[-1]
    assert (
        p.get_attribute("#dp-speak", "aria-pressed") == "true"
        and p.inner_text("#dp-speak").strip() == "Stop reading"
    )
    p.evaluate(
        "__said[2] && __said[2].onstart && __said[2].onstart()"
    )  # the voice reaches step 2: the list follows
    assert p.get_attribute(".dp-step[data-i='1']", "aria-current") == "step"
    p.click("#dp-speak")
    assert p.evaluate("__said.length") == 0 and p.get_attribute("#dp-speak", "aria-pressed") == "false"
    p.click("#dp-speak")
    p.evaluate("AtlasRouting.close()")  # closing the panel stops the voice
    assert p.evaluate("__said.length") == 0
    assert p.errors == [], p.errors
    p.context.close()


def test_no_read_aloud_button_without_speech_support(browser, cdn, site):
    p = _new_page(browser, cdn, viewport={"width": 1280, "height": 800})
    p.add_init_script(
        "Object.defineProperty(window, 'speechSynthesis', {configurable: true, value: undefined}); window.SpeechSynthesisUtterance = undefined;"
    )
    p.goto(f"{site}/oxford.html" + route_hash([39.5079, -84.7368], [39.5088, -84.7345]))
    wait_state(p, "route")
    assert p.is_hidden("#dp-speak")
    p.context.close()
