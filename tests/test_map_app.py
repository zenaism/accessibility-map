# ruff: noqa: E501
"""The new map app (B1) in a real browser (Playwright + Chromium): search, results, place card, details, saved places,
route steps with a simulated position, theme, events, and measured accessibility at 375 and 1280 px in Light and Dark.

Pages are rendered into a temporary site with the Oxford graph and served over HTTP. Leaflet is vendored in the page (atlas.leaflet).
once and served locally; the basemap tiles are replaced by a blank image (nothing leaves the machine)."""

import functools
import http.server
import json
import re
import shutil
import threading

import pytest

from atlas import leaflet, map_app, ui_checks
from atlas.core import ROOT

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

CDN = [
    "leaflet@1.9.4/dist/leaflet.css",
    "leaflet@1.9.4/dist/leaflet.js",
    "leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
    "leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
]
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201a5f6458b0000000049454e44ae426082"
)
GRAPH = ROOT / "data" / "map" / "routing" / "oxford.graph.json"


def _data():
    old = (ROOT / "data" / "map" / "oxford.html").read_text()
    raw = old.split("const DATA = ", 1)[1].split(", RATINGS = ", 1)[0]
    return json.loads(raw.replace("\\u003c", "<"))


# ---------------------------------------------------------------- static


def test_render_has_no_template_leftovers_and_uses_the_foundation():
    html = map_app.render(_data(), "Oxford")
    assert "__" not in re.sub(
        r"__MAP(CFG|DATA)|__ROUTECORE|__esModule|__proto__|__defineGetter__|__lookup",
        "",
        html.split("<body", 1)[1].split("window.__MAPDATA", 1)[0],
    )
    assert "data-theme" in html and "atlasTheme" in html and 'class="tabbar four"' in html
    assert html.count('data-atlas-emit="atlas:open-report"') >= 2 and "atlas:open-ask" in html
    assert "/*__NAV__*/" not in html


def test_no_third_party_requests_except_the_basemap_and_the_database():
    html = map_app.render(
        {"oxford": {"generated": "x", "features": []}}, "Oxford"
    )  # the data (source links) is not a request
    html = html.replace(leaflet.head(), "")  # the vendored library has links in its comments: not requests
    urls = set(re.findall(r"https?://[^\s'\")<>]+", html))
    hosts = {re.sub(r"^https?://([^/]+).*", r"\1", u) for u in urls}
    allowed = {
        "basemap.nationalmap.gov",
        "www.google.com",
        "github.com",
        "www.w3.org",
        "127.0.0.1",
    }
    allowed |= {
        h for h in hosts if h.endswith(".supabase.co")
    }  # the rating and report form talks to the project database
    assert hosts <= allowed, hosts - allowed


# ---------------------------------------------------------------- browser


@pytest.fixture(scope="module")
def cdn():
    """Leaflet is vendored in the page now (atlas.leaflet): nothing is downloaded. Kept so tests keep their signature."""
    return {}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    (root / "oxford.html").write_text(map_app.render(_data(), "Oxford"))
    if GRAPH.exists():
        (root / "routing").mkdir()
        shutil.copy(GRAPH, root / "routing" / "oxford.graph.json")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium not available ({e})")
        yield b
        b.close()


def open_map(browser, cdn, site, width=375, height=812, theme="light", init=None, hash_=""):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        permissions=["geolocation"],
        geolocation={"latitude": 39.5075, "longitude": -84.734, "accuracy": 10},
    )
    ctx.add_init_script(
        f"try{{localStorage.setItem('atlas.theme','{theme}');if(!localStorage.getItem('atlas-region'))localStorage.setItem('atlas-region','oxford')}}catch(e){{}}"
    )
    if init:
        ctx.add_init_script(init)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on(
        "console",
        lambda m: (
            pg.errors.append(m.text)
            if m.type == "error" and "Failed to load resource" not in m.text
            else None
        ),
    )
    pg.requests = []
    pg.on("request", lambda r: pg.requests.append(r.url))

    pg.route(
        "**/basemap.nationalmap.gov/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG)
    )
    pg.goto(f"{site}/oxford.html{hash_}")
    pg.wait_for_selector("html[data-map-ready]")
    return pg


def search(pg, text="library"):
    pg.fill("#q", text)
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")


def open_first(pg):
    pg.locator("[data-open]").first.click()
    pg.wait_for_selector(".stat3")


def test_empty_start_is_search_first(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    assert pg.locator(".pin").count() == 0 and pg.locator(".cluster").count() == 0
    assert pg.get_by_text("Map is empty. Search or pick a type.").is_visible()
    assert [t.inner_text() for t in pg.locator(".tile").all()] == [
        "Restrooms",
        "Parking",
        "Entrances",
        "Parks",
        "Trails",
        "Open now",
    ]
    assert (
        pg.get_by_role("button", name="Near me").is_visible()
        and pg.get_by_role("link", name="Ask").first.is_visible()
    )
    assert pg.get_by_role("button", name="Browse A to Z").is_visible()
    assert [a.get_attribute("aria-label") for a in pg.locator(".tabbar .tab").all()] == [
        "Map",
        "Saved",
        "Ask",
        "Report a problem",
    ]
    assert not pg.errors


def test_typing_suggests_enter_searches_and_selecting_opens_the_card(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.fill("#q", "lib")
    pg.wait_for_selector("#sug [role=option]")
    assert pg.get_attribute("#q", "aria-expanded") == "true" and pg.get_attribute("#sug", "role") == "listbox"
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    assert pg.locator("#rows .badge").count() >= 1
    assert re.match(r"\d+ places?", pg.locator("#h-res").inner_text())
    open_first(pg)
    assert pg.get_by_role("button", name="Route here").is_visible()
    assert pg.locator(".stat3 .stat").count() == 3 and pg.locator("select, .leaflet-popup").count() == 0
    assert not pg.errors


def test_no_results_state(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.fill("#q", "zzzzqq")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".state")
    assert "No places match" in pg.locator(".state").inner_text()
    pg.get_by_role("button", name="Clear search").last.click()
    assert pg.get_by_text("Search, or pick a type.").is_visible()


def test_details_first_layer_then_more(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    search(pg)
    open_first(pg)
    pg.get_by_role("button", name="More details").click()
    pg.wait_for_selector(".dfact")
    first = pg.locator("#panel-body").inner_text()
    assert "Access facts" in first and "Entrance" in first and "Restroom" in first and "Parking" in first
    assert pg.locator("#more-det").is_hidden()
    pg.get_by_role("button", name="More details").click()
    assert (
        pg.locator("#more-det").is_visible()
        and pg.get_attribute("[data-more-details]", "aria-expanded") == "true"
    )
    pg.get_by_role("button", name="Back").locator("visible=true").first.click()
    assert pg.locator(".stat3").is_visible()


def test_save_persists_lists_removes_with_undo_and_marks_changes(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    search(pg)
    open_first(pg)
    pg.locator("[data-save]").click()
    ids = json.loads(pg.evaluate("localStorage.getItem('atlas-favs')"))
    assert len(ids) == 1
    pg.locator("a[data-tab=saved]:visible").first.click()
    pg.wait_for_selector(".favrow")
    assert pg.locator(".favrow").count() == 1 and pg.get_by_text("1 saved place").is_visible()
    # a changed rating since saving shows under "Needs a look"
    pg.evaluate(
        "(id) => { const s = JSON.parse(localStorage.getItem('atlas-fav-snap')); s[id].r = 'unknown'; localStorage.setItem('atlas-fav-snap', JSON.stringify(s)); }",
        ids[0],
    )
    pg.reload()
    pg.wait_for_selector("html[data-map-ready]")
    pg.locator("a[data-tab=saved]:visible").first.click()
    pg.wait_for_selector(".favrow.look")
    assert (
        "Needs a look" in pg.locator("#panel-body").inner_text()
        and "Rating changed" in pg.locator(".favrow.look").inner_text()
    )
    pg.get_by_role("button", name="Edit list").click()
    pg.get_by_role("button", name=re.compile("^Remove")).click()
    assert json.loads(pg.evaluate("localStorage.getItem('atlas-favs')")) == []
    pg.get_by_role("button", name="Undo").click()
    assert len(json.loads(pg.evaluate("localStorage.getItem('atlas-favs')"))) == 1
    assert not pg.errors


def test_restore_link_adds_or_replaces(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    ids = pg.evaluate("AtlasMap.ITEMS.slice(0, 3).map(i => i.p.link_id)")
    pg.evaluate("(ids) => localStorage.setItem('atlas-favs', JSON.stringify([ids[0]]))", ids)
    pg.reload()
    pg.wait_for_selector("html[data-map-ready]")
    pg.goto(pg.url.split("#")[0] + "#saved=" + ",".join(ids[1:]))
    pg.reload()
    pg.wait_for_selector("html[data-map-ready]")
    pg.wait_for_selector("[data-restore-do]")
    assert "Add to my list" in pg.locator("[role=radiogroup]").inner_text()
    pg.get_by_role("radio", name="Replace my list").click()
    pg.get_by_role("button", name="Restore").click()
    assert json.loads(pg.evaluate("localStorage.getItem('atlas-favs')")) == ids[1:]


def test_open_now_understands_simple_hours_and_never_guesses(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    f = "([h, d]) => AtlasMap.openNow(h, new Date(d))"
    assert pg.evaluate(f, ["Mo-Fr 09:00-17:00", "2026-11-23T10:00:00"]) is True  # Monday
    assert pg.evaluate(f, ["Mo-Fr 09:00-17:00", "2026-11-23T18:00:00"]) is False
    assert (
        pg.evaluate(f, ["Mo-Fr 09:00-17:00", "2026-11-22T10:00:00"]) is None
    )  # Sunday: no rule matches, so not known
    assert pg.evaluate(f, ["Mo-Fr 09:00-17:00; Sa 10:00-14:00", "2026-11-28T11:00:00"]) is True
    assert pg.evaluate(f, ["24/7", "2026-11-22T03:00:00"]) is True
    assert pg.evaluate(f, ["sunrise-sunset", "2026-11-22T03:00:00"]) is None
    assert pg.evaluate(f, [None, "2026-11-22T03:00:00"]) is None


def test_report_and_ask_fire_events_and_fall_back_to_links(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    href = pg.locator(".tabbar a[data-tab=report]").get_attribute("href")
    assert (
        href.startswith("https://github.com/")
        and pg.locator(".tabbar a[data-tab=ask]").get_attribute("href") == "ask.html"
    )
    pg.evaluate(
        "(() => { window.__ev = []; ['atlas:open-report', 'atlas:open-ask'].forEach(n => atlas.on(n, d => __ev.push([n, d]))); })()"
    )
    pg.locator(".tabbar a[data-tab=report]").click()
    if pg.locator(".rp").count():  # the report form (B2) listens for the same event and opens
        pg.keyboard.press("Escape")
    search(pg)
    open_first(pg)
    pg.get_by_role("button", name="More details").click()
    pg.get_by_role("button", name="Report a problem here").click()
    if pg.locator(".rp").count():
        pg.keyboard.press("Escape")
    ev = pg.evaluate("__ev")
    assert (
        ev[0] == ["atlas:open-report", {}]
        and ev[1][0] == "atlas:open-report"
        and ev[1][1]["region"] == "oxford"
        and ev[1][1]["placeId"]
    )
    assert pg.url.endswith("oxford.html")  # the listener took over: no navigation


def test_settings_switches_theme_and_keeps_the_map_light(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.get_by_role("button", name="Settings").click()
    pg.wait_for_selector("[role=dialog]")
    pg.locator("input[name=atlas-theme][value=dark]").click()
    assert pg.evaluate("atlasTheme.get()") == "dark"
    assert (
        pg.evaluate("getComputedStyle(document.querySelector('#map')).backgroundColor")
        == "rgb(228, 231, 233)"
    )
    pg.keyboard.press("Escape")
    assert pg.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"


@pytest.mark.skipif(not GRAPH.exists(), reason="walking graph not exported")
def test_route_here_then_follow_with_a_simulated_position_and_arrive(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    search(pg)
    open_first(pg)
    pg.get_by_role("button", name="Route here").click()
    pg.wait_for_selector("[data-nav=start]")
    model = pg.evaluate("AtlasNav.N.model")
    assert model["source"] == "graph" and len(model["steps"]) >= 3
    line = model["line"]
    pg.context.set_geolocation({"latitude": line[0][1], "longitude": line[0][0], "accuracy": 8})
    pg.locator("[data-nav=start]").click()
    pg.wait_for_selector(".stepcard")
    assert "Step 1 of" in pg.locator(".stepcard").inner_text()
    mid = line[len(line) * 2 // 3]
    pg.context.set_geolocation({"latitude": mid[1], "longitude": mid[0], "accuracy": 8})
    pg.wait_for_function("!document.querySelector('.stepcard').innerText.includes('Step 1 of')")
    pg.context.set_geolocation({"latitude": mid[1], "longitude": mid[0], "accuracy": 120})
    pg.wait_for_selector("text=Location is rough. Arrow is off.")
    end = line[-1]
    pg.context.set_geolocation({"latitude": end[1], "longitude": end[0], "accuracy": 8})
    pg.wait_for_selector("text=You are here")
    assert pg.evaluate("AtlasNav.N.watch") is None  # location watching stops on arrival
    assert not [r for r in pg.requests if "127.0.0.1" not in r and "nationalmap" not in r]


def test_stop_and_resume_and_denied(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    search(pg)
    open_first(pg)
    pg.get_by_role("button", name="Route here").click()
    pg.wait_for_selector("[data-nav=start]")
    pg.locator("[data-nav=start]").click()
    pg.wait_for_selector(".stepcard")
    pg.get_by_role("button", name="Stop").click()
    assert pg.evaluate("AtlasNav.N.watch") is None
    pg.wait_for_selector("text=Location is off. The route stays here.")
    pg.get_by_role("button", name="Resume").click()
    pg.wait_for_selector(".stepcard")


def test_denied_permission_leaves_the_steps_usable(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.context.clear_permissions()
    search(pg)
    open_first(pg)
    pg.get_by_role("button", name="Route here").click()
    pg.wait_for_selector("[data-nav=start]")
    pg.locator("[data-nav=start]").click()
    pg.wait_for_selector("text=Location is off. Use the steps by hand.")
    pg.get_by_role("button", name="Next step").click()
    assert "Step 2 of" in pg.locator(".stepcard").inner_text()


def test_keyboard_only_search_to_save(browser, cdn, site):
    pg = open_map(browser, cdn, site, width=1280, height=720)
    pg.focus("#q")
    pg.keyboard.type("library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    pg.locator("[data-open]").first.focus()
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".stat3")
    pg.get_by_role("button", name="Save").focus()
    pg.keyboard.press("Space")
    assert len(json.loads(pg.evaluate("localStorage.getItem('atlas-favs')"))) == 1
    assert pg.evaluate("document.activeElement.closest('#panel') !== null")


@pytest.mark.parametrize("width,height", [(375, 812), (1280, 720)])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_measured_accessibility_of_each_state(browser, cdn, site, width, height, theme):
    pg = open_map(browser, cdn, site, width, height, theme)
    failures = []

    def measure(state):
        m = pg.evaluate(ui_checks.JS_MEASURE)
        for key, kind in (("contrast", "text"), ("icons", "icon"), ("borders", "border")):
            for r in m[key]:
                if r["ratio"] < r["need"] - 1e-9 and "leaflet" not in r["el"]:
                    failures.append(f"{state}: {kind} {r['ratio']:.2f} < {r['need']}: {r['el']}")
        for t in m["targets"]:
            if (t["w"] < 43.99 or t["h"] < 43.99) and "leaflet" not in t["el"]:
                failures.append(f"{state}: target {t['w']}x{t['h']}: {t['el']}")
        for n in m["names"]:
            if not n["name"] and "leaflet" not in n["el"]:
                failures.append(f"{state}: no name: {n['el']}")
        if m["scroll"]["sw"] > m["scroll"]["cw"]:
            failures.append(f"{state}: horizontal scroll")

    measure("start")
    pg.fill("#q", "lib")
    pg.wait_for_selector("#sug [role=option]")
    measure("typing")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    measure("results")
    open_first(pg)
    measure("card")
    pg.get_by_role("button", name="More details").click()
    pg.wait_for_selector(".dfact")
    pg.get_by_role("button", name="More details").click()
    measure("details")
    pg.get_by_role("button", name="Back").locator("visible=true").first.click()
    pg.locator("a[data-tab=saved]:visible").first.click()
    measure("saved empty")
    if GRAPH.exists():
        pg.get_by_role("button", name="Back").locator("visible=true").first.click()
        pg.get_by_role("button", name="Route here").click()
        pg.wait_for_selector("[data-nav=start]")
        measure("route preview")
        pg.locator("[data-nav=start]").click()
        pg.wait_for_selector(".stepcard")
        measure("route follow")
    assert failures == [], "\n".join(failures)
    assert not pg.errors


def test_200_percent_zoom_has_no_sideways_scroll_and_keeps_controls_reachable(browser, cdn, site):
    pg = open_map(browser, cdn, site, width=188, height=406)  # 375 x 812 at 200 percent
    for step in ("start", "results", "card"):
        if step == "results":
            search(pg)
        if step == "card":
            open_first(pg)
        assert pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), (
            step
        )
    assert pg.get_by_role("button", name="Route here").scroll_into_view_if_needed() is None
    assert pg.get_by_role("button", name="Save").is_visible()


@pytest.mark.skipif(
    ui_checks.find_axe() is None,
    reason="axe-core not installed (npm install axe-core@4.10.2 --no-save --prefix ./.axe)",
)
@pytest.mark.parametrize("width,height,theme", [(375, 812, "light"), (1280, 720, "dark")])
def test_axe_finds_nothing_in_each_state(browser, cdn, site, width, height, theme):
    pg = open_map(browser, cdn, site, width, height, theme)
    pg.add_script_tag(path=str(ui_checks.find_axe()))
    run = "async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).slice(0, 3).join(' | '))"
    found = {"start": pg.evaluate(run)}
    pg.fill("#q", "lib")
    pg.wait_for_selector("#sug [role=option]")
    found["typing"] = pg.evaluate(run)
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    found["results"] = pg.evaluate(run)
    open_first(pg)
    found["card"] = pg.evaluate(run)
    pg.get_by_role("button", name="More details").click()
    pg.wait_for_selector(".dfact")
    pg.get_by_role("button", name="More details").click()
    found["details"] = pg.evaluate(run)
    if GRAPH.exists():
        pg.get_by_role("button", name="Route here").click()
        pg.wait_for_selector("[data-nav=start]")
        found["route preview"] = pg.evaluate(run)
        pg.locator("[data-nav=start]").click()
        pg.wait_for_selector(".stepcard")
        found["route follow"] = pg.evaluate(run)
    assert {k: v for k, v in found.items() if v} == {}


def test_the_saved_link_from_other_pages_opens_the_saved_places_view(browser, cdn, site):
    pg = open_map(browser, cdn, site, hash_="#saved")
    assert (
        pg.get_by_role("heading", name="Saved places", level=2).count() == 1
        or "No saved places yet" in pg.locator("#panel-body").inner_text()
    )
    assert pg.locator(".tabbar .tab[aria-current=page]").get_attribute("data-tab") == "saved"


def test_a_source_with_no_date_says_so_instead_of_leaving_it_out(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.fill("#q", "library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    open_first(pg)
    t = pg.locator(".conf").first.inner_text()
    assert re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}|no date given", t), t


def test_copy_link_is_one_tap_on_the_place_card(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.fill("#q", "library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    open_first(pg)
    pg.evaluate(
        "window.__copied = null; navigator.clipboard.writeText = (t) => { window.__copied = t; return Promise.resolve(); }"
    )
    btn = pg.get_by_role("button", name=re.compile("^Copy link to"))
    assert btn.bounding_box()["width"] >= 44 and btn.bounding_box()["height"] >= 44
    btn.click()
    link = pg.evaluate("window.__copied")
    assert "#place=" in link and "region=" in link
    assert pg.locator(".toast", has_text="Link copied.").count() == 1
