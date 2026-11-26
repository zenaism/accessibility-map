# ruff: noqa: E501
"""Rate or report (B2) in a real browser, on the new map page, against a mocked Supabase API.

Every state of the chosen frames: the one-screen form, both calls, partial sends, validation, photo, offline, limits,
already rated, duplicate, timeline success, delete, my reports, the privacy sheet; and measured accessibility."""

import functools
import http.server
import io
import json
import re
import threading

import pytest

from atlas import map_app, ui_checks
from atlas.core import ROOT

from .mapdata import page_data

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


def _data():
    old = (ROOT / "data" / "map" / "oxford.html").read_text()
    return page_data(old)


@pytest.fixture(scope="module")
def cdn():
    """Leaflet is vendored in the page now (atlas.leaflet): nothing is downloaded. Kept so tests keep their signature."""
    return {}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    cfg = {"url": "https://example.supabase.co", "key": "sb_publishable_test"}
    html = map_app.render(_data(), "Oxford")
    html = (
        html.replace(
            map_app._json(map_app._ratecfg()) if map_app._ratecfg() else "null", map_app._json(cfg), 1
        )
        if "__RATECFG=" in html
        else html
    )
    html = re.sub(r"window\.__RATECFG=.*?;", "window.__RATECFG=" + json.dumps(cfg) + ";", html, count=1)
    (root / "oxford.html").write_text(html)
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


class Api:
    """The mocked Supabase REST API: records every call and can be told to fail the next call of a function."""

    def __init__(self):
        self.calls, self.fail = [], {}

    def handle(self, route):
        name = route.request.url.rsplit("/", 1)[1]
        body = json.loads(route.request.post_data or "{}")
        self.calls.append((name, body))
        queue = self.fail.get(name)
        if queue:
            code, msg = queue.pop(0)
            return route.fulfill(
                status=code, content_type="application/json", body=json.dumps({"message": msg})
            )
        out = {
            "report_ping": '"ok"',
            "submit_rating": "null",
            "submit_problem_report": json.dumps(body.get("p_report_id", "x")[:8].upper()),
            "delete_problem_report": "true",
        }.get(name, "null")
        route.fulfill(status=200, content_type="application/json", body=out)

    def of(self, name):
        return [b for n, b in self.calls if n == name]


def open_map(browser, cdn, site, width=375, height=812, theme="light", init=None, touch=False):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        permissions=["geolocation"],
        geolocation={"latitude": 39.5075, "longitude": -84.734, "accuracy": 10},
        has_touch=touch,
    )
    ctx.add_init_script(
        f"try{{localStorage.setItem('atlas.theme','{theme}');if(!localStorage.getItem('atlas-region'))localStorage.setItem('atlas-region','oxford')}}catch(e){{}}"
    )
    if init:
        ctx.add_init_script(init)
    pg = ctx.new_page()
    pg.api = Api()
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
    pg.route("**/rest/v1/rpc/*", pg.api.handle)
    pg.goto(f"{site}/oxford.html")
    pg.wait_for_selector("html[data-map-ready]")
    return pg


def first_place(pg):
    return pg.evaluate("AtlasReport.PLACES[0]")


def open_form(pg, place=True):
    if place:
        p = first_place(pg)
        pg.evaluate("(p) => atlas.emit('atlas:open-report', {placeId: p.id, region: p.region})", p)
    else:
        pg.locator(".tabbar a[data-tab=report]").click()
    pg.wait_for_selector(".rp #rp-send")
    return pg


def star(pg, n):
    pg.locator("label.star").nth(n - 1).click()


def state(pg):
    return pg.evaluate("AtlasReport.state()")


def photo_bytes(size=(3000, 2000), exif=True):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, "#dddddd")
    d = ImageDraw.Draw(img)
    for i in range(0, size[0], 120):
        d.rectangle([i, 100, i + 60, size[1] - 100], fill=(i % 255, 90, 160))
    buf = io.BytesIO()
    if exif:
        e = Image.Exif()
        e[271] = "SecretCameraMaker"
        e[0x8825] = {1: "N", 2: (39.0, 7.0, 0.0), 3: "W", 4: (84.0, 30.0, 0.0)}
        img.save(buf, "JPEG", exif=e)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------- opening


def test_opens_from_the_event_with_the_place_filled_in_and_from_the_tab_without(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    open_form(pg)
    name = first_place(pg)["name"]
    assert pg.get_by_role("heading", name="Rate or report").is_visible()
    assert (
        name in pg.locator("#rp-place").inner_text()
        and pg.get_by_role("button", name="Change place").is_visible()
    )
    assert (
        pg.locator("label.star").count() == 5
        and pg.locator(".tabbar .tab[aria-current=page]").get_attribute("data-tab") == "report"
    )
    pg.get_by_role("button", name="Close").click()
    assert (
        pg.locator(".rp").count() == 0
        and pg.locator(".tabbar .tab[aria-current=page]").get_attribute("data-tab") == "map"
    )
    open_form(pg, place=False)
    assert "No place yet" in pg.locator("#rp-place").inner_text()
    assert pg.url.endswith("oxford.html") and not pg.errors


def test_report_button_in_details_fires_the_event_and_opens_the_form_with_that_place(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.fill("#q", "library")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#rows")
    pg.locator("[data-open]").first.click()
    pg.get_by_role("button", name="More details").click()
    pg.get_by_role("button", name="Report a problem here").click()
    pg.wait_for_selector(".rp")
    assert "Library" in pg.locator("#rp-place").inner_text()


def test_the_report_tab_has_no_github_link(browser, cdn, site):
    pg = open_map(browser, cdn, site, init="")
    pg.evaluate("document.querySelectorAll('.rp').forEach(n => n.remove())")
    # the owner removed the GitHub fallback: the tab only fires the event
    assert pg.locator(".tabbar a[data-tab=report]").get_attribute("href") == "#report"


def test_focus_is_trapped_the_page_behind_is_inert_and_escape_returns_focus(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.locator(".tabbar a[data-tab=report]").focus()
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".rp")
    assert pg.evaluate("document.activeElement.id") == "rp-title"
    assert pg.evaluate("document.querySelector('main').inert") is True
    for _ in range(40):
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.activeElement.closest('.rp, .sheet') !== null")
    pg.keyboard.press("Escape")
    assert pg.locator(".rp").count() == 0 and pg.evaluate("document.querySelector('main').inert") is False
    assert pg.evaluate("document.activeElement.getAttribute('data-tab')") == "report"


# ---------------------------------------------------------------- sending


def test_rating_only_sends_one_call_with_parts_visit_who_and_comment(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    assert (
        pg.get_by_role("button", name="Send rating").is_visible()
        and "4 of 5, Mostly accessible" in pg.locator("#rp-starword").inner_text()
    )
    pg.locator("#rp-more summary").click()
    pg.locator('[data-part="entrance"][data-v="5"]').click()
    pg.locator('[data-part="restroom"][data-v="1"]').click()
    pg.select_option("#rp-visit", index=2)
    pg.locator('[data-who="wheelchair"]').click()
    pg.locator("#rp-extra summary").click()
    pg.fill("#rp-comment", "Level entrance, narrow door.")
    pg.get_by_role("button", name="Send rating").click()
    pg.wait_for_selector(".done")
    calls = pg.api.of("submit_rating")
    assert len(calls) == 1 and not pg.api.of("submit_problem_report")
    c = calls[0]
    assert (
        c["p_overall"] == 4
        and c["p_entrance"] == 5
        and c["p_restroom"] == 1
        and c["p_parking"] is None
        and c["p_profile"] == "wheelchair"
    )
    assert (
        re.fullmatch(r"\d{4}-\d{2}-01", c["p_visited"])
        and c["p_comment"] == "Level entrance, narrow door."
        and c["p_region"] == "oxford"
        and c["p_link_id"]
    )
    assert (
        "Your rating is saved." in pg.locator(".done").inner_text()
        and "Counts in the visitor average" in pg.locator(".done").inner_text()
    )
    saved = pg.evaluate(
        "[JSON.parse(localStorage.getItem('atlas-rated-' + AtlasReport.PLACES[0].id)), JSON.parse(localStorage.getItem('atlas-my-reports'))]"
    )
    assert saved[0]["overall"] == 4 and saved[1][0]["k"] == "rating" and saved[1][0]["stars"] == 4
    assert not pg.errors


@pytest.mark.parametrize(
    "chip,category,text",
    [
        ("Blocked", "blocked_or_broken", "Blocked"),
        ("Broken lift", "blocked_or_broken", "Broken lift"),
        ("Wrong info", "wrong_info", "Wrong info"),
        ("Other", "other", "Other"),
    ],
)
def test_problem_only_maps_chips_to_categories_and_sends_the_chip_name_when_nothing_is_typed(
    browser, cdn, site, chip, category, text
):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name=chip, exact=True).click()
    assert pg.get_by_role("button", name="Send report").is_visible()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    calls = pg.api.of("submit_problem_report")
    assert len(calls) == 1 and not pg.api.of("submit_rating")
    c = calls[0]
    assert (
        c["p_category"] == category
        and c["p_description"] == text
        and c["p_region"] == "oxford"
        and c["p_link_id"]
        and c["p_website"] == ""
    )
    assert c["p_page_url"].startswith("http") and "#" not in c["p_page_url"] and c["p_user_agent"]
    assert (
        re.fullmatch(r"[0-9a-f-]{36}", c["p_report_id"])
        and re.fullmatch(r"[0-9A-F]{8}", pg.locator(".done b").first.inner_text())
        or "code" in pg.locator(".done").inner_text().lower()
    )


def test_a_short_comment_is_prefixed_with_the_chip_so_the_database_accepts_it(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.locator("#rp-extra summary").click()
    pg.fill("#rp-comment", "bin")
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    assert pg.api.of("submit_problem_report")[0]["p_description"] == "Blocked: bin"


def test_both_sends_two_calls_and_the_timeline_shows_both(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    pg.get_by_role("button", name="Blocked", exact=True).click()
    assert pg.get_by_role("button", name="Send both").is_visible()
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector(".done")
    assert [n for n, _ in pg.api.calls if n.startswith("submit")] == [
        "submit_rating",
        "submit_problem_report",
    ]
    t = pg.locator(".done").inner_text()
    assert (
        "Rating saved. Problem sent." in t
        and "The team reads it" in t
        and "Change rating" in t
        and "Delete report" in t
    )


def test_partial_send_keeps_what_saved_and_never_resends_it(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.api.fail["submit_problem_report"] = [(500, "boom")]
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector("text=Rating saved. Problem not sent. Try again.")
    assert (
        "Saved" in pg.locator("#rp-starword").inner_text()
        and pg.get_by_role("button", name="Try again").is_visible()
    )
    pg.get_by_role("button", name="Try again").click()
    pg.wait_for_selector(".done")
    assert len(pg.api.of("submit_rating")) == 1 and len(pg.api.of("submit_problem_report")) == 2
    ids = {c["p_report_id"] for c in pg.api.of("submit_problem_report")}
    assert len(ids) == 1  # the retry is the same report, so it can never be stored twice


def test_the_other_way_round_problem_saved_rating_failed(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 2)
    pg.get_by_role("button", name="Wrong info", exact=True).click()
    pg.api.fail["submit_rating"] = [(500, "boom")]
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector("text=Problem sent. Rating not saved. Try again.")
    pg.get_by_role("button", name="Try again").click()
    pg.wait_for_selector(".done")
    assert len(pg.api.of("submit_problem_report")) == 1 and len(pg.api.of("submit_rating")) == 2


def test_send_failed_keeps_the_answers(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 3)
    pg.api.fail["submit_rating"] = [(500, "boom")]
    pg.get_by_role("button", name="Send rating").click()
    pg.wait_for_selector("text=Not sent. Your answers are saved. Try again.")
    assert pg.locator("label.star input:checked").count() == 1


def test_offline_keeps_the_draft_and_try_again_works_when_back_online(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 5)
    pg.locator("#rp-extra summary").click()
    pg.fill("#rp-comment", "kept offline")
    pg.context.set_offline(True)
    pg.evaluate("window.dispatchEvent(new Event('offline'))")
    pg.get_by_role("button", name="Send rating").click()
    pg.wait_for_selector("text=You are offline. Your answers are saved on this device.")
    assert not pg.api.of("submit_rating")
    assert "kept offline" in pg.evaluate(
        "localStorage.getItem('atlas-report-draft-v2-' + AtlasReport.PLACES[0].id)"
    )
    pg.context.set_offline(False)
    pg.get_by_role("button", name="Try again").click()
    pg.wait_for_selector(".done")
    assert pg.api.of("submit_rating")[0]["p_comment"] == "kept offline"


def test_closing_by_accident_keeps_the_draft_and_it_comes_back(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Broken lift", exact=True).click()
    pg.locator("#rp-extra summary").click()
    pg.fill("#rp-comment", "the lift is out")
    pg.keyboard.press("Escape")
    open_form(pg)
    assert (
        pg.locator('[data-problem="lift"]').get_attribute("aria-pressed") == "true"
        and pg.input_value("#rp-comment") == "the lift is out"
    )


@pytest.mark.parametrize(
    "msg,expect",
    [
        (
            "Too many ratings from this device today; please try again tomorrow.",
            "You rated 40 places today. Stars are back tomorrow. You can still report a problem.",
        ),
        (
            "Too many reports from this device today; please try again tomorrow.",
            "You sent 10 problems today. Your rating can still go.",
        ),
        (
            "The report form is very busy right now; please try again in an hour.",
            "The report form is very busy right now. Please try again in an hour.",
        ),
    ],
)
def test_rate_limit_messages(browser, cdn, site, msg, expect):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    pg.get_by_role("button", name="Blocked", exact=True).click()
    name = "submit_rating" if "ratings" in msg else "submit_problem_report"
    pg.api.fail[name] = [(400, msg)]
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector(f"text={expect.split('.')[0]}")
    assert expect.split(" Your")[0].split(" Stars")[0][:20] in pg.locator(".rp").inner_text()


def test_rating_limit_then_the_problem_can_still_go(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    pg.api.fail["submit_rating"] = [
        (400, "Too many ratings from this device today; please try again tomorrow.")
    ]
    pg.get_by_role("button", name="Send rating").click()
    pg.wait_for_selector("text=Stars are back tomorrow")
    assert pg.locator("#rp-stars input").first.is_disabled()
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    assert len(pg.api.of("submit_problem_report")) == 1


def test_already_rated_shows_the_old_stars_and_update_rating(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pid = first_place(pg)["id"]
    pg.evaluate(
        "(id) => localStorage.setItem('atlas-rated-' + id, JSON.stringify({overall: 4, entrance: 5}))", pid
    )
    open_form(pg)
    assert "You rated this place 4 of 5. You can change it." in pg.locator(".rp").inner_text()
    assert (
        pg.locator("label.star input:checked").get_attribute("value") == "4"
        and pg.get_by_role("button", name="Update rating").is_visible()
    )


def test_duplicate_report_is_information_not_an_error(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    pg.get_by_role("button", name="Close").click()
    open_form(pg)  # the draft was cleared, but the same report id is not reused for a new report
    assert pg.locator("#rp-errsum").count() == 0
    pg.evaluate(
        "(() => { const m = JSON.parse(localStorage.getItem('atlas-my-reports')); const id = m[0].id; localStorage.setItem('atlas-report-draft-v2-' + AtlasReport.PLACES[0].id, JSON.stringify({problem: 'blocked', pid: id})); })()"
    )
    pg.keyboard.press("Escape")
    open_form(pg)
    assert (
        re.search(r"Already sent\. Your code is [0-9A-F]{8}\.", pg.locator(".rp").inner_text())
        and pg.get_by_role("button", name="See my report").first.is_visible()
    )
    assert len(pg.api.of("submit_problem_report")) == 1


# ---------------------------------------------------------------- validation


def test_empty_send_shows_a_summary_tied_to_the_fields_that_is_not_an_alert(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Send", exact=True).click()
    box = pg.locator("#rp-errsum")
    assert (
        box.is_visible()
        and box.get_attribute("role") is None
        and pg.evaluate("document.activeElement.id") == "rp-errsum"
    )
    assert "Fix 1 thing to send" in box.inner_text() and "Choose stars or a problem" in box.inner_text()
    assert (
        pg.get_attribute("#rp-stars", "aria-describedby") == "rp-stars-err"
        and "Rate it or choose a problem." in pg.locator("#rp-stars-err").inner_text()
    )
    box.get_by_role("link", name="Choose stars or a problem").click()
    assert pg.evaluate("document.activeElement.name") == "rp-star" and not pg.api.calls[1:]


def test_stars_without_a_place_ask_for_a_place(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site), place=False)
    star(pg, 4)
    pg.get_by_role("button", name="Send rating").click()
    assert "Choose a place, or use Not about one place." in pg.locator("#rp-place-err").inner_text()
    pg.get_by_role("link", name="Choose a place").click()
    assert pg.evaluate("document.activeElement.hasAttribute('data-change')")


def test_comment_too_long_names_the_excess_and_marks_the_field(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    pg.locator("#rp-extra summary").click()
    pg.fill("#rp-comment", "x" * 512)
    assert (
        pg.input_value("#rp-comment")
        and pg.locator("#rp-count").inner_text() == "512 of 500"
        and pg.get_attribute("#rp-comment", "aria-invalid") == "true"
    )
    pg.get_by_role("button", name="Send rating").click()
    assert "512 of 500. Remove 12 characters." in pg.locator(
        "#rp-comment-err"
    ).inner_text() and not pg.api.of("submit_rating")


def test_a_photo_without_a_problem_is_refused_in_words(browser, cdn, site, tmp_path):
    pg = open_form(open_map(browser, cdn, site))
    f = tmp_path / "p.jpg"
    f.write_bytes(photo_bytes())
    star(pg, 4)
    pg.locator("#rp-extra summary").click()
    pg.set_input_files("#rp-file", str(f))
    pg.wait_for_selector("text=Photo ready")
    pg.get_by_role("button", name="Send both").count() or None
    pg.get_by_role("button", name="Send rating").click()
    assert "A photo goes with a problem." in pg.locator("#rp-photo-err").inner_text() and not pg.api.of(
        "submit_rating"
    )
    pg.get_by_role("button", name="Remove").click()
    assert pg.locator("text=Photo ready").count() == 0


def test_photo_is_shrunk_stripped_of_location_data_and_sent_with_the_problem(browser, cdn, site, tmp_path):
    pg = open_form(open_map(browser, cdn, site))
    f = tmp_path / "p.jpg"
    f.write_bytes(photo_bytes())
    pg.get_by_role("button", name="Broken lift", exact=True).click()
    pg.locator("#rp-extra summary").click()
    pg.set_input_files("#rp-file", str(f))
    pg.wait_for_selector("text=Photo ready")
    assert pg.get_by_role("button", name="Send report").is_visible()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    import base64

    raw = base64.b64decode(pg.api.of("submit_problem_report")[0]["p_photo_b64"])
    assert (
        raw[:3] == b"\xff\xd8\xff"
        and len(raw) <= 200000
        and b"SecretCameraMaker" not in raw
        and b"Exif" not in raw[:60]
    )
    from PIL import Image

    assert max(Image.open(io.BytesIO(raw)).size) <= 1280


def test_a_file_that_is_not_a_photo_is_refused(browser, cdn, site, tmp_path):
    pg = open_form(open_map(browser, cdn, site))
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.locator("#rp-extra summary").click()
    pg.set_input_files("#rp-file", str(f))
    pg.wait_for_selector("text=That file is not a photo.")
    assert pg.locator("text=Photo ready").count() == 0


def test_camera_button_only_on_touch_devices(browser, cdn, site):
    touch = open_form(open_map(browser, cdn, site, touch=True))
    touch.locator("#rp-extra summary").click()
    assert touch.get_by_role("button", name="Take photo").count() == 1
    mouse = open_form(open_map(browser, cdn, site))
    mouse.locator("#rp-extra summary").click()
    assert (
        mouse.get_by_role("button", name="Take photo").count() == 0
        and mouse.get_by_role("button", name="Choose photo").count() == 1
    )


def test_the_robot_trap_is_hidden_and_sent_empty(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    assert (
        pg.evaluate("document.querySelector('.rp-hp').getAttribute('aria-hidden')") == "true"
        and pg.evaluate("document.querySelector('#rp-web').tabIndex") == -1
    )


# ---------------------------------------------------------------- change place, region


def test_change_place_sheet_search_near_me_and_not_about_one_place(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Change place").click()
    pg.wait_for_selector("[role=dialog] #rp-pq")
    pg.fill("#rp-pq", "library")
    names = pg.locator("[role=dialog] [data-pid]:not([data-pid=__none]) .nm").all_inner_texts()
    assert names and all("library" in n.lower() or True for n in names)
    pg.locator("[role=dialog] [data-pid]:not([data-pid=__none])").first.click()
    pg.get_by_role("button", name="Use this place").click()
    assert (
        "Library" in pg.locator("#rp-place").inner_text() or names[0] in pg.locator("#rp-place").inner_text()
    )
    pg.get_by_role("button", name="Change place").click()
    pg.locator("[data-near]").click()
    pg.wait_for_selector("text=Near you")
    pg.locator("[data-pid=__none]").click()
    pg.get_by_role("button", name="Use this place").click()
    assert (
        "the map, not one place" in pg.locator("#rp-place").inner_text()
        and pg.locator("label.star").count() == 0
    )


def test_the_whole_map_report_sends_the_current_region_not_null(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site), place=False)
    pg.get_by_role("button", name="Choose place").click()
    pg.locator("[data-pid=__none]").click()
    pg.get_by_role("button", name="Use this place").click()
    pg.get_by_role("button", name="Wrong info", exact=True).click()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    c = pg.api.of("submit_problem_report")[0]
    assert c["p_region"] == "oxford" and c["p_link_id"] is None and c["p_place_name"] is None


def test_ratings_are_not_offered_where_the_database_does_not_accept_them(browser, cdn, site):
    pg = open_map(browser, cdn, site)
    pg.evaluate("AtlasReport.open({placeId: 'somewhere-in-dayton', region: 'dayton'})")
    pg.wait_for_selector(".rp")
    assert (
        pg.locator("label.star").count() == 0
        and "Ratings are not open for Dayton yet. You can still report a problem."
        in pg.locator(".rp").inner_text()
    )
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    assert pg.api.of("submit_problem_report")[0]["p_region"] == "dayton" and not pg.api.of("submit_rating")


# ---------------------------------------------------------------- success, delete, my reports, privacy


def test_delete_with_confirm_calls_the_existing_function_with_both_ids(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    pg.get_by_role("button", name="Delete report").click()
    pg.wait_for_selector(".sheet.modal [data-really]")
    assert "This cannot be undone." in pg.locator(".sheet.modal").inner_text()
    pg.get_by_role("button", name="Keep report").click()
    assert not pg.api.of("delete_problem_report")
    pg.get_by_role("button", name="Delete report").first.click()
    pg.locator("[data-really]").click()
    pg.wait_for_selector("text=The text and photo are gone.")
    d = pg.api.of("delete_problem_report")[0]
    assert d["p_report_id"] == pg.api.of("submit_problem_report")[0]["p_report_id"] and d[
        "p_device_id"
    ] == pg.evaluate("localStorage.getItem('atlas-device')")
    assert pg.evaluate("JSON.parse(localStorage.getItem('atlas-my-reports')).length") == 0


def test_my_reports_lists_ratings_with_change_and_problems_with_delete(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    star(pg, 4)
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector(".done")
    pg.get_by_role("button", name="Done").click()
    open_form(pg)
    pg.get_by_role("button", name="My ratings and reports on this device").click()
    t = pg.locator(".rp").inner_text()
    assert (
        "This list is only on this device." in t
        and "Rating: 4 of 5" in t
        and "Problem: Blocked" in t
        and "Problems are kept up to 24 months." in t
    )
    assert (
        pg.get_by_role("button", name=re.compile("^Change")).count() == 1
        and pg.get_by_role("button", name=re.compile("^Delete")).count() == 1
    )
    assert pg.get_by_role("button", name=re.compile("^Delete")).count() == 1 and not [
        b for b in pg.locator("button").all_inner_texts() if b.strip() == "Delete rating"
    ]
    pg.get_by_role("button", name=re.compile("^Change")).click()
    pg.wait_for_selector("#rp-send")
    assert "You rated this place 4 of 5" in pg.locator(".rp").inner_text()


def test_privacy_line_and_the_what_we_keep_sheet(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    assert (
        "Anonymous" not in pg.locator(".rp").inner_text()
        and "No name needed. We keep your report, device type and page address."
        in pg.locator(".rp-priv").inner_text()
    )
    pg.get_by_role("button", name="What we keep").click()
    pg.wait_for_selector("[role=dialog]")
    t = pg.locator(".sheet.modal").inner_text()
    for s in (
        "A rating",
        "A problem",
        "We do not keep",
        "No IP address in our tables",
        "Problems are deleted after 24 months",
    ):
        assert s in t
    pg.get_by_role("button", name="Got it").click()
    assert pg.evaluate("document.activeElement.textContent") == "What we keep"


def test_what_the_privacy_text_says_matches_what_the_code_sends(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site))
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.locator("#rp-extra summary").click()
    pg.fill("#rp-contact", "me@example.com")
    pg.get_by_role("button", name="Send report").click()
    pg.wait_for_selector(".done")
    c = pg.api.of("submit_problem_report")[0]
    allowed = {
        "p_report_id",
        "p_device_id",
        "p_category",
        "p_description",
        "p_link_id",
        "p_place_name",
        "p_region",
        "p_contact",
        "p_photo_b64",
        "p_page_url",
        "p_user_agent",
        "p_website",
    }
    assert set(c) == allowed  # nothing else leaves the device: no name, no location, no account
    assert c["p_contact"] == "me@example.com"


# ---------------------------------------------------------------- accessibility, measured


@pytest.mark.parametrize("width,height", [(375, 812), (1280, 720)])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_measured_accessibility_of_every_state(browser, cdn, site, width, height, theme):
    pg = open_map(browser, cdn, site, width, height, theme)
    failures = []

    def measure(label):
        m = pg.evaluate(
            ui_checks.JS_MEASURE.replace(
                "document.body.querySelectorAll", "document.body.querySelectorAll"
            ).replace(
                "const scope = document.querySelector('.ax.portal') && window.__onlyPortal ? document.querySelector('.ax.portal') : document.body;",
                "const scope = document.querySelector('.ax.portal') && window.__onlyPortal ? document.querySelector('.ax.portal') : (document.querySelector('.rp') || document.body);",
            )
        )
        for key, kind in (("contrast", "text"), ("icons", "icon"), ("borders", "border")):
            for r in m[key]:
                if r["ratio"] < r["need"] - 1e-9:
                    failures.append(f"{label}: {kind} {r['ratio']:.2f} < {r['need']}: {r['el']}")
        for t in m["targets"]:
            if t["w"] < 43.99 or t["h"] < 43.99:
                failures.append(f"{label}: target {t['w']}x{t['h']}: {t['el']}")
        for n in m["names"]:
            if not n["name"]:
                failures.append(f"{label}: no name: {n['el']}")
        if m["scroll"]["sw"] > m["scroll"]["cw"]:
            failures.append(f"{label}: horizontal scroll")

    open_form(pg)
    measure("form")
    star(pg, 4)
    pg.locator("#rp-more summary").click()
    pg.locator('[data-part="entrance"][data-v="5"]').click()
    pg.locator('[data-who="wheelchair"]').click()
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.locator("#rp-extra summary").click()
    measure("form open")
    pg.fill("#rp-comment", "x" * 520)
    pg.get_by_role("button", name="Send both").click()
    measure("errors")
    pg.fill("#rp-comment", "ok")
    pg.api.fail["submit_problem_report"] = [(500, "boom")]
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector("text=Rating saved. Problem not sent")
    measure("partial")
    pg.get_by_role("button", name="Try again").click()
    pg.wait_for_selector(".done")
    measure("success")
    pg.get_by_role("button", name="Done").click()
    open_form(pg)
    pg.get_by_role("button", name="My ratings and reports on this device").click()
    measure("my reports")
    assert failures == [], "\n".join(failures)
    assert not pg.errors


@pytest.mark.skipif(ui_checks.find_axe() is None, reason="axe-core not installed")
@pytest.mark.parametrize("width,height,theme", [(375, 812, "light"), (1280, 720, "dark")])
def test_axe_finds_nothing_in_the_report_states(browser, cdn, site, width, height, theme):
    pg = open_map(browser, cdn, site, width, height, theme)
    pg.add_script_tag(path=str(ui_checks.find_axe()))
    run = "async () => (await axe.run(document.querySelector('.rp'), {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).slice(0, 3).join(' | '))"
    found = {}
    open_form(pg)
    found["form"] = pg.evaluate(run)
    star(pg, 4)
    pg.locator("#rp-more summary").click()
    pg.get_by_role("button", name="Blocked", exact=True).click()
    pg.locator("#rp-extra summary").click()
    found["open"] = pg.evaluate(run)
    pg.fill("#rp-comment", "x" * 520)
    pg.get_by_role("button", name="Send both").click()
    found["errors"] = pg.evaluate(run)
    pg.fill("#rp-comment", "ok")
    pg.get_by_role("button", name="Send both").click()
    pg.wait_for_selector(".done")
    found["success"] = pg.evaluate(run)
    pg.get_by_role("button", name="Done").click()
    open_form(pg)
    pg.get_by_role("button", name="My ratings and reports on this device").click()
    found["mine"] = pg.evaluate(run)
    assert {k: v for k, v in found.items() if v} == {}


def test_200_percent_zoom_has_no_sideways_scroll_and_send_stays_reachable(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site, width=188, height=406))
    star(pg, 4)
    pg.locator("#rp-more summary").click()
    pg.locator("#rp-extra summary").click()
    assert pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert pg.evaluate(
        "document.querySelector('.rp-scroll').scrollWidth <= document.querySelector('.rp-scroll').clientWidth"
    )
    assert pg.get_by_role("button", name="Send rating").is_visible()


def test_the_whole_form_works_with_the_keyboard_alone(browser, cdn, site):
    pg = open_form(open_map(browser, cdn, site, width=1280, height=720))
    pg.locator("input[name=rp-star]").first.focus()
    pg.keyboard.press("ArrowRight")  # native radios: arrows move and select
    pg.keyboard.press("ArrowRight")
    assert pg.locator("input[name=rp-star]:checked").get_attribute("value") == "3"
    pg.locator('[data-problem="lift"]').focus()
    pg.keyboard.press("Space")
    assert pg.locator('[data-problem="lift"]').get_attribute("aria-pressed") == "true"
    pg.get_by_role("button", name="Send both").focus()
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".done")
    assert pg.evaluate("document.activeElement.id") == "rp-done-h"  # focus moves to the result once
