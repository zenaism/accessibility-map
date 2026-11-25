# ruff: noqa: E501, F401, F811
"""The city switcher (B4) in a real browser: which city opens first (link, saved choice, closest city, Choose a city), the
switcher (sheet on phones, dropdown on desktop), switching in place, limited cities, Saved with cities, shared links, Near
me far from the city, reports that send the current region, and measured accessibility. The device rule for the closest city
is also checked against the Python rule in tests/js/regions.test.js."""

import functools
import http.server
import json
import re
import shutil
import threading

import pytest

from atlas import map_app, ui_checks
from atlas.core import ROOT

from .test_map_app import CDN, PNG, browser, cdn  # fixtures shared with the map tests

pytest.importorskip("playwright")

OXFORD = {"latitude": 39.507, "longitude": -84.745, "accuracy": 10}
CINCINNATI = {"latitude": 39.1031, "longitude": -84.512, "accuracy": 10}
ATLANTIC = {"latitude": 30.0, "longitude": -40.0, "accuracy": 10}
MAPDIR = ROOT / "data" / "map"


def _data(name):
    old = (MAPDIR / f"{name}.html").read_text()
    raw = old.split("const DATA = ", 1)[1].split(", RATINGS = ", 1)[0]
    return json.loads(raw.replace("\\u003c", "<"))


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("region")
    both = {**_data("oxford"), **_data("cincinnati")}
    (root / "index.html").write_text(map_app.render(both, "Both"))  # two cities in the page
    (root / "oxford.html").write_text(
        map_app.render(_data("oxford"), "Oxford")
    )  # one city: the other is fetched
    shutil.copy(MAPDIR / "cincinnati_atlas.geojson", root / "cincinnati_atlas.geojson")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def open_page(
    browser,
    cdn,
    site,
    page="index.html",
    query="",
    hash_="",
    region=None,
    geo=OXFORD,
    width=375,
    height=812,
    theme="light",
    permissions=True,
):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        permissions=["geolocation"] if permissions else [],
        geolocation=geo,
    )
    pre = (
        f"try{{localStorage.setItem('atlas.theme','{theme}');"
        + (f"localStorage.setItem('atlas-region','{region}');" if region else "")
        + "}catch(e){}"
    )
    ctx.add_init_script(pre)
    pg = ctx.new_page()
    pg.errors, pg.calls = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on(
        "console",
        lambda m: (
            pg.errors.append(m.text)
            if m.type == "error" and "Failed to load resource" not in m.text
            else None
        ),
    )
    pg.on("load", lambda _: pg.calls.append("load"))

    def unpkg(route):
        url = route.request.url.split("unpkg.com/", 1)[1]
        f = cdn.get(url)
        route.fulfill(
            status=200 if f else 404,
            content_type="text/css" if url.endswith(".css") else "text/javascript",
            body=f.read_bytes() if f else "",
        )

    pg.route("https://unpkg.com/**", unpkg)
    pg.route(
        "**/basemap.nationalmap.gov/**", lambda r: r.fulfill(status=200, content_type="image/png", body=PNG)
    )
    pg.route(
        "**/rest/v1/rpc/*",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body='"1A2B3C4D"' if r.request.url.endswith("problem_report") else "null",
        ),
    )
    pg.goto(f"{site}/{page}{query}{hash_}")
    pg.wait_for_selector("html[data-map-ready]")
    return pg


def city_button(pg):
    return pg.locator("#city-btn:visible, #city-btn-d:visible").first


def region(pg):
    return pg.evaluate("AtlasMap.S.region")


# ---------------------------------------------------------------- which city opens


def test_the_closest_city_rule_matches_python_on_the_golden_cases():
    import subprocess

    out = subprocess.run(
        ["node", "--test", "tests/js/regions.test.js"], cwd=ROOT, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stdout[-800:]


def test_a_link_region_wins_over_the_saved_choice_and_is_not_saved(browser, cdn, site):
    pg = open_page(browser, cdn, site, query="?region=cincinnati", region="oxford")
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    assert pg.evaluate("localStorage.getItem('atlas-region')") == "oxford"
    assert "Cincinnati, change city" in city_button(pg).get_attribute("aria-label")
    assert (
        "This link is in Cincinnati." in pg.locator("#panel-body").inner_text()
        and pg.get_by_role("button", name="Back to Oxford").is_visible()
    )


def test_the_saved_choice_wins_over_the_position(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="cincinnati", geo=OXFORD)
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    assert pg.locator("#panel-body").get_by_text("Use Oxford?").count() == 0
    assert pg.url.endswith("index.html")  # reopening does not rewrite the address


def test_first_open_in_oxford_asks_use_oxford_and_a_tap_saves_the_choice(browser, cdn, site):
    pg = open_page(browser, cdn, site, geo=OXFORD)
    pg.wait_for_selector("#panel-body >> text=Use Oxford?")
    t = pg.locator("#panel-body").inner_text()
    assert (
        "You seem to be in Oxford." in t
        and "Your position stays on this device." in t
        and pg.get_by_role("button", name="Choose another").is_visible()
    )
    assert region(pg) is None and pg.evaluate("localStorage.getItem('atlas-region')") is None
    pg.get_by_role("button", name="Use Oxford").click()
    pg.wait_for_function("AtlasMap.S.region === 'oxford'")
    assert pg.evaluate("localStorage.getItem('atlas-region')") == "oxford" and "region=oxford" in pg.url


def test_outside_every_city_or_with_location_off_shows_choose_a_city(browser, cdn, site):
    far = open_page(browser, cdn, site, geo=ATLANTIC)
    far.wait_for_selector("#panel-body >> text=Choose a city")
    t = far.locator("#panel-body").inner_text()
    assert (
        "You seem to be outside our cities." in t
        and "Cincinnati" in t
        and "Places, ratings" in t
        and "Oxford" in t
        and "Places, routes, ratings" in t
    )
    assert (
        "Limited data" in t
        and "Washington" in t
        and "Places and curb ramps" in t
        and "Dayton" in t
        and "Places only" in t
        and "More cities coming." in t
    )
    assert "Baltimore" not in t
    denied = open_page(browser, cdn, site, permissions=False)
    denied.wait_for_selector("#panel-body >> text=Choose a city")
    assert "Location is off." in denied.locator("#panel-body").inner_text()


def test_choose_another_shows_the_list_and_picking_a_city_saves_it(browser, cdn, site):
    pg = open_page(browser, cdn, site, geo=OXFORD)
    pg.wait_for_selector("#panel-body >> text=Use Oxford?")
    pg.get_by_role("button", name="Choose another").click()
    pg.get_by_role("radio", name=re.compile("^Cincinnati")).click()
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    assert pg.evaluate("localStorage.getItem('atlas-region')") == "cincinnati"


# ---------------------------------------------------------------- the switcher


def test_the_city_button_names_the_city_and_opens_a_sheet_on_phones(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford")
    b = pg.locator("#city-btn")
    assert b.get_attribute("aria-label") == "Oxford, change city" and b.bounding_box()["height"] >= 44
    b.click()
    pg.wait_for_selector(".sheet.modal")
    t = pg.locator(".sheet.modal").inner_text()
    assert (
        "Choose a city" in t
        and "Places, ratings" in t
        and "Places, routes, ratings" in t
        and "Limited data" in t
        and "Places and curb ramps" in t
    )
    assert pg.locator(".sheet.modal [aria-checked=true]").inner_text().startswith("Oxford") and pg.evaluate(
        "document.querySelector('main').closest('[inert]') !== null"
    )
    pg.keyboard.press("Escape")
    assert pg.locator(".sheet.modal").count() == 0 and pg.evaluate("document.activeElement.id") == "city-btn"


def test_on_desktop_the_switcher_is_a_dropdown_that_does_not_hide_the_map(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford", width=1280, height=720)
    b = pg.locator("#city-btn-d")
    b.click()
    pop = pg.locator("#city-pop")
    assert pop.is_visible() and pg.locator(".sheet.modal").count() == 0 and "Limited data" in pop.inner_text()
    pg.keyboard.press("Escape")
    assert pop.is_hidden() and pg.evaluate("document.activeElement.id") == "city-btn-d"
    b.click()
    pg.mouse.click(900, 500)
    assert pop.is_hidden()


def test_switching_happens_in_place_with_loading_then_showing_and_the_event(browser, cdn, site):
    pg = open_page(browser, cdn, site, page="oxford.html", region="oxford")
    pg.evaluate("(() => { window.__ev = []; atlas.on('atlas:region-changed', (d) => __ev.push(d)); })()")
    n0 = len(pg.calls)
    pg.locator("#city-btn").click()
    pg.get_by_role("radio", name=re.compile("^Cincinnati")).click()
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    pg.wait_for_selector("#region-pill >> text=Showing Cincinnati")
    assert len(pg.calls) == n0 and pg.evaluate("__ev") == [
        {"region": "cincinnati"}
    ]  # no page load: the data was fetched
    assert (
        pg.evaluate("localStorage.getItem('atlas-region')") == "cincinnati" and "region=cincinnati" in pg.url
    )
    assert (
        pg.evaluate("AtlasMap.results().every(i => i.p.region === 'cincinnati')")
        and pg.evaluate("AtlasMap.results().length") > 100
    )
    assert pg.evaluate("atlasRegion()") == "cincinnati"
    c = pg.evaluate("AtlasMap.map.getCenter()")
    assert abs(c["lat"] - 39.1365) < 0.02


def test_a_failed_switch_keeps_the_old_city_and_try_again_works(browser, cdn, site):
    pg = open_page(browser, cdn, site, page="oxford.html", region="oxford")
    pg.route("**/cincinnati_atlas.geojson", lambda r: r.abort())
    pg.locator("#city-btn").click()
    pg.get_by_role("radio", name=re.compile("^Cincinnati")).click()
    pg.wait_for_selector("#region-pill >> text=Could not load Cincinnati. You are still in Oxford.")
    assert region(pg) == "oxford" and pg.evaluate("localStorage.getItem('atlas-region')") == "oxford"
    pg.unroute("**/cincinnati_atlas.geojson")
    pg.get_by_role("button", name="Try again").click()
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")


def test_an_open_search_keeps_its_words_and_reruns_in_the_new_city(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford")
    pg.fill("#q", "library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    ox = pg.evaluate("AtlasMap.results().map(i => i.p.name)")
    pg.locator("#city-btn").click()
    pg.get_by_role("radio", name=re.compile("^Cincinnati")).click()
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    assert pg.input_value("#q") == "library"
    t = pg.locator("#panel-body").inner_text()
    assert "Your search stays. Results are for Cincinnati now." in t and "Search Oxford instead" in t
    assert (
        pg.evaluate("AtlasMap.results().every(i => i.p.region === 'cincinnati')")
        and pg.evaluate("AtlasMap.results().map(i => i.p.name)") != ox
    )
    pg.get_by_role("button", name="Search Oxford instead").click()
    pg.wait_for_function("AtlasMap.S.region === 'oxford'")
    assert pg.input_value("#q") == "library"


# ---------------------------------------------------------------- limited cities


def test_a_limited_city_says_less_data_here_and_the_dismissal_is_remembered(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="dayton")
    pg.wait_for_function("AtlasMap.S.region === 'dayton'")
    t = pg.locator("#panel-body").inner_text()
    assert "Less data here" in t and "Places only. Ratings not open yet." in t
    pg.get_by_role("button", name="Got it").click()
    assert (
        "Less data here" not in pg.locator("#panel-body").inner_text()
        and pg.evaluate("localStorage.getItem('atlas-notice-dayton')") == "1"
    )
    pg.reload()
    pg.wait_for_selector("html[data-map-ready]")
    pg.wait_for_function("AtlasMap.S.region === 'dayton'")
    assert "Less data here" not in pg.locator("#panel-body").inner_text()


def test_limited_cities_have_no_stars_and_a_problem_report_carries_the_city(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="dc")
    pg.wait_for_function("AtlasMap.S.region === 'dc'")
    pg.locator("a[data-tab=report]:visible").first.click()
    pg.wait_for_selector(".rp #rp-send")
    pg.get_by_role("button", name="Choose place").click()
    pg.locator("[data-pid=__none]").click()
    pg.get_by_role("button", name="Use this place").click()
    pg.get_by_role("button", name="Blocked", exact=True).click()
    calls = []
    pg.route(
        "**/rest/v1/rpc/submit_problem_report",
        lambda r: (
            calls.append(json.loads(r.request.post_data)),
            r.fulfill(status=200, content_type="application/json", body='"1A2B3C4D"'),
        ),
    )
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    assert calls[0]["p_region"] == "dc" and calls[0]["p_link_id"] is None


# ---------------------------------------------------------------- saved places, links, near me


def test_saved_places_store_the_city_and_the_list_shows_a_tag_and_a_filter(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford")
    ids = pg.evaluate(
        "[AtlasMap.ITEMS.find(i => i.p.region === 'oxford').p.link_id, AtlasMap.ITEMS.find(i => i.p.region === 'cincinnati').p.link_id]"
    )
    pg.evaluate(
        "(ids) => localStorage.setItem('atlas-favs', JSON.stringify(ids))", ids
    )  # an old list: ids only
    pg.reload()
    pg.wait_for_selector("html[data-map-ready]")
    pg.wait_for_function("AtlasMap.S.region === 'oxford'")
    v2 = json.loads(pg.evaluate("localStorage.getItem('atlas-favs-v2')"))
    assert {x["region"] for x in v2} == {"oxford", "cincinnati"} and [
        x["id"] for x in v2
    ] == ids  # migrated by lookup
    pg.locator("a[data-tab=saved]:visible").first.click()
    pg.wait_for_selector(".favrow")
    t = pg.locator("#panel-body").inner_text()
    assert "2 saved places in 2 cities" in t and t.count("Oxford") >= 2 and "Cincinnati" in t
    pg.get_by_role("button", name="Show only Oxford").click()
    t = pg.locator("#panel-body").inner_text()
    assert (
        "1 saved in Oxford" in t
        and "1 saved in another city is hidden." in t
        and "Open a place in another city and the map switches to that city." in t
    )
    pg.get_by_role("button", name="Show only Oxford").click()
    pg.get_by_role("button", name=re.compile("^Open .* in Cincinnati|^Open")).last.click()
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    pg.wait_for_selector(".stat3")


def test_saving_a_place_stores_id_and_region_and_keeps_the_plain_ids_for_the_old_page(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford")
    pg.fill("#q", "library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    pg.locator("[data-open]").first.click()
    pg.locator("[data-save]").click()
    v2 = json.loads(pg.evaluate("localStorage.getItem('atlas-favs-v2')"))
    assert v2[0]["region"] == "oxford" and json.loads(pg.evaluate("localStorage.getItem('atlas-favs')")) == [
        v2[0]["id"]
    ]


def test_a_copied_link_carries_the_city_and_opening_it_in_another_city_shows_a_way_back(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="cincinnati")
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    pg.fill("#q", "library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    pg.locator("[data-open]").first.click()
    pg.get_by_role("button", name="More details").click()
    pg.get_by_role("button", name="More details").click()
    pg.evaluate(
        "window.__copied = null; navigator.clipboard.writeText = (t) => { window.__copied = t; return Promise.resolve(); }"
    )
    pg.locator("[data-copy]").click()
    link = pg.evaluate("window.__copied")
    assert "region=cincinnati" in link and "#place=" in link
    other = open_page(
        browser, cdn, site, region="oxford", query="?region=cincinnati", hash_=link[link.index("#") :]
    )
    other.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    other.wait_for_selector(".dfact, .stat3")
    assert (
        "This link is in Cincinnati." in other.locator("#panel-body").inner_text()
        and other.get_by_role("button", name="Back to Oxford").is_visible()
    )
    other.get_by_role("button", name="Back to Oxford").click()
    other.wait_for_function("AtlasMap.S.region === 'oxford'")


def test_near_me_far_from_the_city_asks_before_switching(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford", geo=CINCINNATI)
    pg.get_by_role("button", name="Near me").click()
    pg.wait_for_selector("#panel-body >> text=You are far from Oxford. Switch to Cincinnati?")
    assert region(pg) == "oxford"
    pg.get_by_role("button", name="Stay in Oxford").click()
    assert region(pg) == "oxford" and pg.locator("#panel-body").get_by_text("far from").count() == 0
    pg.get_by_role("button", name="Near me").click()
    pg.get_by_role("button", name="Switch to Cincinnati").click()
    pg.wait_for_function("AtlasMap.S.region === 'cincinnati'")
    pg.wait_for_selector("#rows")


def test_near_me_outside_every_city_offers_choose_a_city(browser, cdn, site):
    pg = open_page(browser, cdn, site, region="oxford", geo=ATLANTIC)
    pg.get_by_role("button", name="Near me").click()
    pg.wait_for_selector("#panel-body >> text=You are outside our cities.")
    assert "Near me works inside a covered city." in pg.locator("#panel-body").inner_text()
    pg.get_by_role("button", name="Choose a city").click()
    assert "Limited data" in pg.locator("#panel-body").inner_text()


# ---------------------------------------------------------------- the assistant says which city


def test_no_city_names_are_written_into_the_map_files():
    for f in ("map.js", "nav.js", "regionui.js", "region.js"):
        text = (ROOT / "src/atlas/web/map" / f).read_text()
        assert not re.search(r"['\"](cincinnati|oxford|dayton|dc|baltimore)['\"]", text, re.I), f
    app = (ROOT / "src/atlas/map_app.py").read_text()
    assert not re.search(r"['\"](cincinnati|oxford|dayton|dc|baltimore)['\"]", app), "map_app.py"


# ---------------------------------------------------------------- accessibility, measured


@pytest.mark.parametrize("width,height", [(375, 812), (1280, 720)])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_measured_accessibility_of_the_city_states(browser, cdn, site, width, height, theme):
    failures = []

    def measure(pg, label):
        m = pg.evaluate(
            ui_checks.JS_MEASURE.replace(
                "const scope = document.querySelector('.ax.portal') && window.__onlyPortal ? document.querySelector('.ax.portal') : document.body;",
                "const scope = document.querySelector('.sheet.modal') || document.querySelector('#city-pop:not([hidden])') || document.body;",
            )
        )
        for key, kind in (("contrast", "text"), ("icons", "icon"), ("borders", "border")):
            for r in m[key]:
                if r["ratio"] < r["need"] - 1e-9 and "leaflet" not in r["el"]:
                    failures.append(f"{label}: {kind} {r['ratio']:.2f} < {r['need']}: {r['el']}")
        for t in m["targets"]:
            if (t["w"] < 43.99 or t["h"] < 43.99) and "leaflet" not in t["el"]:
                failures.append(f"{label}: target {t['w']}x{t['h']}: {t['el']}")
        failures.extend(
            f"{label}: no name: {n['el']}" for n in m["names"] if not n["name"] and "leaflet" not in n["el"]
        )
        if m["scroll"]["sw"] > m["scroll"]["cw"]:
            failures.append(f"{label}: horizontal scroll")

    pg = open_page(browser, cdn, site, geo=OXFORD, width=width, height=height, theme=theme)
    pg.wait_for_selector("#panel-body >> text=Use Oxford?")
    measure(pg, "use Oxford")
    pg.get_by_role("button", name="Choose another").click()
    measure(pg, "choose a city")
    pg.get_by_role("radio", name=re.compile("^Dayton")).click()
    pg.wait_for_function("AtlasMap.S.region === 'dayton'")
    pg.wait_for_selector("text=Less data here")
    measure(pg, "limited notice")
    pg.locator("#city-btn:visible, #city-btn-d:visible").first.click()
    pg.wait_for_selector(".sheet.modal, #city-pop:not([hidden])")
    measure(pg, "switcher open")
    pg.keyboard.press("Escape")
    pg2 = open_page(
        browser, cdn, site, region="oxford", geo=CINCINNATI, width=width, height=height, theme=theme
    )
    pg2.get_by_role("button", name="Near me").click()
    pg2.wait_for_selector("#panel-body >> text=You are far from Oxford.")
    measure(pg2, "near me far")
    assert failures == [], "\n".join(failures)
    assert not pg.errors and not pg2.errors


@pytest.mark.skipif(ui_checks.find_axe() is None, reason="axe-core not installed")
@pytest.mark.parametrize("width,height,theme", [(375, 812, "light"), (1280, 720, "dark")])
def test_axe_finds_nothing_in_the_city_states(browser, cdn, site, width, height, theme):
    pg = open_page(browser, cdn, site, geo=OXFORD, width=width, height=height, theme=theme)
    pg.add_script_tag(path=str(ui_checks.find_axe()))
    run = "async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).slice(0, 3).join(' | '))"
    found = {}
    pg.wait_for_selector("#panel-body >> text=Use Oxford?")
    found["use"] = pg.evaluate(run)
    pg.get_by_role("button", name="Use Oxford").click()
    pg.wait_for_function("AtlasMap.S.region === 'oxford'")
    pg.locator("#city-btn:visible, #city-btn-d:visible").first.click()
    pg.wait_for_selector(".sheet.modal, #city-pop:not([hidden])")
    found["switcher"] = pg.evaluate(run)
    pg.keyboard.press("Escape")
    assert {k: v for k, v in found.items() if v} == {}
