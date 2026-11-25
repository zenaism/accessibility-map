# ruff: noqa: E501
"""The Openway Assistant in a real browser (Playwright + Chromium): tiles and typing, keyboard only, phone width,
live-region announcements, unknown answers, "My needs" with localStorage blocked, voice and photo states, the hooks
to the map, and axe-core (skipped when .axe is not installed: npm install axe-core@4.10.2 --no-save --prefix ./.axe)."""

import base64
import io
import json
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from atlas.assistant import server  # noqa: E402
from atlas.assistant.page import build as _build  # noqa: E402


def build(*a, **k):
    """These tests are for the legacy chat page (the panel inside the old map page); the new chat screen is in tests/test_chat_app.py."""
    return _build(*a, legacy=True, **k)


AXE = Path(".axe/node_modules/axe-core/axe.min.js")
TODAY = "2026-11-20"


@pytest.fixture(scope="module")
def base():
    build()
    s = server.serve(0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()
    s.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, base):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    yield pg
    assert not pg.errors, pg.errors
    ctx.close()


def open_ask(page, base, query=""):
    page.goto(f"{base}/ask.html?today={TODAY}{query}")
    page.wait_for_selector(".ow-tiles button")
    page.wait_for_function(
        "document.querySelector('.ow-compose button[type=submit]') && !document.querySelector('.ow-compose button[type=submit]').disabled"
    )


def ask(page, text):
    page.get_by_label("Your question").fill(text)
    page.keyboard.press("Enter")
    page.wait_for_selector(".ow-a .ow-main")


def run_axe(page):
    page.add_script_tag(path=str(AXE))
    r = page.evaluate(
        "async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']}})).violations.map(v => v.id + ': ' + v.help + ' @ ' + v.nodes.map(n => n.target.join(' ')).slice(0,3).join(' | '))"
    )
    return r


def test_tile_gives_an_answer_with_cards_and_sources(page, base):
    open_ask(page, base)
    page.get_by_role("button", name="Events this week").click()
    page.wait_for_selector(".ow-a .ow-main")
    assert "events" in page.locator(".ow-a .ow-main").first.inner_text().lower()
    assert page.locator(".ow-card").count() >= 1
    page.get_by_role("button", name="Sources").first.click()
    assert page.locator(".ow-sources").first.is_visible()
    assert "Data snapshot: 13 November 2026" in page.locator(".ow-asof").first.inner_text()


def test_typing_a_question_and_the_live_region_is_updated_once(page, base):
    open_ask(page, base)
    page.evaluate("""() => { window.__said = []; const el = document.querySelector('.ow [role=status].ow-vh');
        new MutationObserver(() => { if (el.textContent) window.__said.push(el.textContent); }).observe(el, {childList: true, characterData: true, subtree: true}); }""")
    ask(page, "Does the Art Museum lend wheelchairs?")
    page.wait_for_timeout(300)
    said = page.evaluate("window.__said")
    assert any("Cincinnati Art Museum lists wheelchair loan" in s for s in said)
    assert sum("lists wheelchair loan" in s for s in said) == 1  # announced once, not twice
    assert "Wheelchair loan: yes" in page.locator(".ow-card").first.inner_text()
    # the focus is still in the question box: the answer does not steal it
    assert page.evaluate("document.activeElement.type") == "text" and page.evaluate(
        "document.activeElement.closest('form') !== null"
    )


def test_keyboard_only(page, base):
    open_ask(page, base)
    page.get_by_label("Your question").focus()
    page.keyboard.type("closest accessible restroom near downtown")
    page.keyboard.press("Enter")
    page.wait_for_selector(".ow-a .ow-main")
    # reach "More detail" with Tab and open it with Enter
    for _ in range(40):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.textContent.trim()") == "More detail":
            break
    assert page.evaluate("document.activeElement.textContent.trim()") == "More detail"
    page.keyboard.press("Enter")
    assert page.locator(".ow-detail").first.is_visible()
    assert page.evaluate("document.activeElement.getAttribute('aria-expanded')") == "true"
    # settings open and close with the keyboard; Escape returns focus to the Settings button
    page.get_by_role("button", name="Settings").focus()
    page.keyboard.press("Enter")
    assert page.locator(".ow-settings").is_visible()
    page.keyboard.press("Escape")
    assert not page.locator(".ow-settings").is_visible()
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Settings"


def test_every_control_has_a_name_and_a_big_enough_target(page, base):
    open_ask(page, base)
    ask(page, "closest accessible restroom near downtown")
    small = page.evaluate("""() => [...document.querySelectorAll('.ow button, .ow a.ow-btn, .ow input[type=text]')]
        .filter(e => e.offsetParent !== null)
        .map(e => [e.textContent.trim() || e.getAttribute('aria-label') || e.id, Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)])
        .filter(([n, w, h]) => h < 44 || w < 44)""")
    assert not small, small
    nameless = page.evaluate("""() => [...document.querySelectorAll('.ow button, .ow a, .ow input')].filter(e => e.offsetParent !== null && e.getAttribute('aria-hidden') !== 'true' && !(e.textContent.trim() || e.getAttribute('aria-label') || (e.labels && e.labels.length)))
        .map(e => e.outerHTML.slice(0, 80))""")
    assert not nameless, nameless


def test_phone_viewport_has_no_sideways_scroll(browser, base):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    open_ask(pg, base)
    ask(pg, "Find food with no steps near OTR")
    w = pg.evaluate(
        "[document.documentElement.scrollWidth, window.innerWidth, document.querySelector('.ow-log').scrollWidth, document.querySelector('.ow-log').clientWidth]"
    )
    assert w[0] <= w[1] and w[2] <= w[3] + 1, w
    pg.get_by_role("button", name="Settings").click()
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
    ctx.close()


def test_zoom_320_wide(browser, base):
    ctx = browser.new_context(viewport={"width": 320, "height": 640})
    pg = ctx.new_page()
    open_ask(pg, base)
    ask(pg, "What events are on this weekend in Oxford?")
    assert pg.evaluate("document.documentElement.scrollWidth") <= 320
    ctx.close()


def test_unknown_questions_are_honest(page, base):
    open_ask(page, base)
    ask(page, "Where can I see a waterfall without stairs?")
    text = page.locator(".ow-a").last.inner_text()
    assert "I don't have anything about waterfall" in text and "I don't know" in text
    assert not page.locator(".ow-card").count()
    ask(page, "Is there accessible housing near Oxford?")
    assert "don't have information about accessible housing yet" in page.locator(".ow-a").last.inner_text()
    ask(page, "Is the Aronoff Center ADA compliant?")
    last = page.locator(".ow-a").last.inner_text()
    assert "can't say whether a place is ADA compliant" in last
    ask(page, "I need an ambulance")
    assert "call 911 now" in page.locator(".ow-a").last.inner_text()
    assert page.locator(".ow-a.ow-emergency").count() == 1
    # the unknown questions are saved on this device only
    gaps = json.loads(page.evaluate("localStorage.getItem('openway.gaps')"))
    assert len(gaps) >= 2


def test_my_needs_with_storage_blocked(browser, base):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(
        "Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }});"
    )
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    open_ask(pg, base)
    pg.get_by_role("button", name="Settings").click()
    pg.get_by_role("button", name="My needs").click()
    dlg = pg.get_by_role("dialog")
    assert dlg.is_visible()
    dlg.get_by_label("No, I cannot use steps").check()
    dlg.get_by_label("A screen reader").check()
    dlg.get_by_role("button", name="Save").click()
    assert "this visit only" in pg.locator(".ow-status").inner_text()
    ask(pg, "Find food near downtown")  # the steps answer changes the search to step-free entrances
    assert pg.locator(".ow-a").last.inner_text()
    assert not errs, errs
    # focus returns to where it was
    assert pg.evaluate("document.activeElement.getAttribute('aria-label')") in ("Settings", "")
    ctx.close()


def test_my_needs_are_saved_on_the_device_and_clearable(page, base):
    open_ask(page, base)
    page.get_by_role("button", name="Settings").click()
    page.get_by_role("button", name="My needs").click()
    dlg = page.get_by_role("dialog")
    dlg.get_by_label("Cane or guide").check()
    dlg.get_by_label("Large text").check()
    dlg.get_by_role("button", name="Save").click()
    saved = json.loads(page.evaluate("localStorage.getItem('openway.needs')"))
    assert saved["mobility"] == "cane" and "large_text" in saved["rely"]
    assert (
        page.evaluate("document.querySelector('.ow').style.getPropertyValue('--ow-scale')") == "1.25"
    )  # large text turned on
    page.reload()
    page.wait_for_selector(".ow-tiles button")
    page.get_by_role("button", name="Settings").click()
    page.get_by_role("button", name="My needs").click()
    assert page.get_by_role("dialog").get_by_label("Cane or guide").is_checked()
    page.get_by_role("button", name="Clear my answers").click()
    assert page.evaluate("localStorage.getItem('openway.needs')") is None


def test_text_size_and_plain_language(page, base):
    open_ask(page, base)
    page.get_by_role("button", name="Settings").click()
    page.get_by_label("Extra large").check(force=True)
    assert page.evaluate("document.querySelector('.ow').style.getPropertyValue('--ow-scale')") == "1.5"
    assert (
        page.evaluate("parseFloat(getComputedStyle(document.querySelector('.ow-welcome p')).fontSize)") >= 22
    )
    page.get_by_role("switch", name="Plain language (shorter sentences)").check()
    page.keyboard.press("Escape")
    page.get_by_label("Your question").fill("closest accessible restroom near downtown")
    page.keyboard.press("Enter")
    page.wait_for_selector(".ow-a .ow-main")
    assert page.locator(".ow-main").first.inner_text().startswith("Closest with")


def test_clarifying_question_has_buttons_and_asks_only_once(page, base):
    open_ask(page, base)
    ask(page, "Where is the closest accessible restroom?")
    assert "Where are you?" in page.locator(".ow-a .ow-main").last.inner_text()
    assert page.get_by_role("button", name="Use my location").count() == 1
    page.get_by_role("button", name="Downtown Cincinnati").click()
    page.wait_for_function("document.querySelectorAll('.ow-a').length >= 2")
    assert "closest place I found" in page.locator(".ow-a .ow-main").last.inner_text()


def test_voice_unavailable_is_explained_in_words(browser, base):
    ctx = browser.new_context()
    ctx.add_init_script("delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
    pg = ctx.new_page()
    open_ask(pg, base)
    pg.get_by_role("button", name="Speak").click()
    assert "Voice input is not available in this browser" in pg.locator(".ow-status").inner_text()
    ctx.close()


def test_voice_input_fills_the_question_box(browser, base):
    ctx = browser.new_context()
    ctx.add_init_script("""
      class FakeRec { start() { setTimeout(() => { this.onstart && this.onstart();
          this.onresult({resultIndex: 0, results: [Object.assign([{transcript: 'events this weekend in Oxford'}], {isFinal: true})]});
          this.onend && this.onend(); }, 20); } stop() {} }
      window.SpeechRecognition = FakeRec;""")
    pg = ctx.new_page()
    open_ask(pg, base)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_function("document.querySelector('.ow-compose input[type=text]').value.length > 0")
    assert pg.get_by_label("Your question").input_value() == "events this weekend in Oxford"
    assert "send your voice" in pg.locator(".ow-status").inner_text()
    ctx.close()


def test_read_aloud_with_pause_speed_and_stop(browser, base):
    ctx = browser.new_context()
    ctx.add_init_script("""
      window.__spoken = [];
      window.SpeechSynthesisUtterance = function (t) { this.text = t; };
      Object.defineProperty(window, 'speechSynthesis', {configurable: true, value: { speak(u) { window.__spoken.push([u.text, u.rate]); }, cancel() { window.__spoken.push(['cancel']); }, pause() { window.__spoken.push(['pause']); }, resume() { window.__spoken.push(['resume']); } }});""")
    pg = ctx.new_page()
    open_ask(pg, base)
    ask(pg, "Does the Art Museum lend wheelchairs?")
    pg.get_by_role("button", name="Read aloud").first.click()
    assert pg.get_by_role("group", name="Reading controls").is_visible()
    spoken = pg.evaluate("window.__spoken")
    assert spoken[-1][0].startswith("Yes, Cincinnati Art Museum lists wheelchair loan") and spoken[-1][1] == 1
    pg.get_by_role("button", name="Pause").click()
    assert pg.evaluate("window.__spoken.at(-1)[0]") == "pause"
    pg.get_by_label("Speaking speed").select_option("0.8")
    pg.get_by_role("button", name="Stop reading").click()
    assert not pg.get_by_role("group", name="Reading controls").count()
    ctx.close()


def test_read_aloud_unavailable_is_explained(browser, base):
    ctx = browser.new_context()
    ctx.add_init_script(
        "Object.defineProperty(window, 'speechSynthesis', {configurable: true, value: undefined}); delete window.SpeechSynthesisUtterance;"
    )
    pg = ctx.new_page()
    open_ask(pg, base)
    ask(pg, "Does the Art Museum lend wheelchairs?")
    pg.get_by_role("button", name="Read aloud").first.click()
    assert "Reading aloud is not available" in pg.locator(".ow-status").inner_text()
    ctx.close()


def test_photo_in_guided_mode_says_it_needs_the_local_model(page, base):
    open_ask(page, base)
    page.get_by_role("button", name="Photo").click()
    assert "Photo questions need the local model" in page.locator(".ow-status").inner_text()


def jpeg_with_gps() -> bytes:
    from PIL import Image

    im = Image.new("RGB", (2400, 1600), (200, 120, 40))
    exif = im.getexif()
    exif[0x010F] = "TestCam"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (39.0, 6.0, 5.0), "W", (84.0, 30.0, 40.0)
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    assert b"Exif" in buf.getvalue()[:40]
    return buf.getvalue()


def test_photo_is_shrunk_and_stripped_before_it_is_sent(browser, base):
    ctx = browser.new_context()
    pg = ctx.new_page()
    sent = {}

    def health(route):
        route.fulfill(json={"reachable": True, "model": True, "models": ["qwen2.5:3b"], "vision": True})

    def ask_route(route):
        sent.update(json.loads(route.request.post_data))
        ev = [
            {"type": "text", "kind": "answer", "delta": "In your photo I can see: an orange rectangle."},
            {"type": "meta", "as_of": None, "notes": [], "plan": None, "engine": "vision"},
            {"type": "done", "verified": False, "removed": 0},
        ]
        route.fulfill(
            body="".join("data: " + json.dumps(e) + "\n\n" for e in ev), content_type="text/event-stream"
        )

    pg.route("**/api/health", health)
    pg.route("**/api/ask", ask_route)
    open_ask(pg, base)
    pg.get_by_role("button", name="Settings").click()
    pg.wait_for_function("!document.querySelector('.ow-settings input[value=local]').disabled")
    pg.get_by_label("Local model").check(force=True)
    pg.keyboard.press("Escape")
    pg.set_input_files(
        ".ow input[type=file]", {"name": "door.jpg", "mimeType": "image/jpeg", "buffer": jpeg_with_gps()}
    )
    pg.wait_for_selector(".ow-attach img")
    assert "location data is removed" in pg.locator(".ow-status").inner_text()
    pg.get_by_label("Your question").fill("What does this sign say?")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".ow-a .ow-main")
    raw = base64.b64decode(sent["image"])
    assert raw[:2] == b"\xff\xd8" and b"Exif" not in raw[:64] and b"TestCam" not in raw and b"GPS" not in raw
    from PIL import Image

    assert max(Image.open(io.BytesIO(raw)).size) <= 768
    assert "orange rectangle" in pg.locator(".ow-a .ow-main").inner_text()
    assert not pg.locator(".ow-attach img").count()  # nothing is kept after the question
    ctx.close()


def test_local_model_unreachable_falls_back_with_a_note(browser, base):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.route("**/api/health", lambda r: r.fulfill(json={"reachable": True, "model": True, "models": []}))
    pg.route("**/api/ask", lambda r: r.abort())
    open_ask(pg, base)
    pg.get_by_role("button", name="Settings").click()
    pg.wait_for_function("!document.querySelector('.ow-settings input[value=local]').disabled")
    pg.get_by_label("Local model").check(force=True)
    pg.keyboard.press("Escape")
    ask(pg, "Does the Art Museum lend wheelchairs?")
    assert "guided mode instead" in pg.locator(".ow-status").inner_text()
    assert "wheelchair loan" in pg.locator(".ow-a .ow-main").last.inner_text()
    ctx.close()


def test_chat_fires_the_hooks_the_map_listens_for(page, base):
    open_ask(page, base)
    page.evaluate("""() => { window.__hooks = [];
        for (const n of ['atlas:show-places', 'atlas:route-to', 'atlas:open-report']) window.addEventListener(n, e => { window.__hooks.push([n, e.detail]); e.preventDefault(); }); }""")
    ask(page, "closest accessible restroom near downtown")
    page.get_by_role("link", name="Route here").first.click()
    page.get_by_role("link", name="Show on map").first.click()
    page.get_by_role("button", name="Show all on map").click() if page.get_by_role(
        "button", name="Show all on map"
    ).count() else None
    page.get_by_role("button", name="Report a problem").first.click()
    hooks = page.evaluate("window.__hooks")
    names = [h[0] for h in hooks]
    assert names[:2] == ["atlas:route-to", "atlas:show-places"] and names[-1] == "atlas:open-report"
    assert hooks[0][1]["profile"] == "wheelchair" and hooks[0][1]["placeId"]
    assert "closest accessible restroom" in hooks[-1][1]["text"]
    assert page.url.endswith("ask.html?today=" + TODAY)  # the map handled them: no navigation


def test_without_a_map_the_buttons_open_the_map_page(page, base):
    open_ask(page, base)
    ask(page, "does the Art Museum lend wheelchairs")
    href = page.get_by_role("link", name="Show on map").first.get_attribute("href")
    assert href.startswith("cincinnati.html#place=cincinnati-art-museum")


def test_data_load_failure_is_explained(browser, base):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.route("**/assistant/oxford.json", lambda r: r.fulfill(status=500, body="no"))
    pg.goto(f"{base}/ask.html")
    pg.wait_for_selector("[role=alert]")
    assert "could not load the data" in pg.locator("[role=alert]").inner_text()
    ctx.close()


@pytest.mark.skipif(not AXE.exists(), reason="axe-core not installed")
@pytest.mark.parametrize("state", ["empty", "answer", "unknown", "settings", "needs", "large", "phone"])
def test_axe_finds_no_violations(browser, base, state):
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844} if state == "phone" else {"width": 1280, "height": 800}
    )
    pg = ctx.new_page()
    open_ask(pg, base)
    if state in ("answer", "phone"):
        ask(pg, "closest accessible restroom near downtown")
        pg.get_by_role("button", name="More detail").first.click()
        pg.get_by_role("button", name="Sources").first.click()
    elif state == "unknown":
        ask(pg, "Where can I see a waterfall without stairs?")
    elif state == "settings":
        pg.get_by_role("button", name="Settings").click()
    elif state == "needs":
        pg.get_by_role("button", name="Settings").click()
        pg.get_by_role("button", name="My needs").click()
    elif state == "large":
        pg.get_by_role("button", name="Settings").click()
        pg.get_by_label("Extra large").check(force=True)
        pg.keyboard.press("Escape")
        ask(pg, "events this weekend in Oxford")
    res = run_axe(pg)
    assert res == [], res
    ctx.close()


def test_the_panel_on_a_map_page(browser, base):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"{base}/oxford.html?today={TODAY}")
    try:
        pg.wait_for_selector("#ask-open", timeout=15000)
        pg.wait_for_function("document.querySelectorAll('#list li').length > 0", timeout=15000)
    except Exception:
        ctx.close()
        pytest.skip("the map page needs Leaflet from unpkg.com (no network)")
    btn = pg.locator("#ask-open")
    assert btn.get_attribute("aria-expanded") == "false"
    btn.click()
    pg.wait_for_selector("#ow-panel .ow-tiles button")
    assert btn.get_attribute("aria-expanded") == "true"
    assert pg.get_by_role("dialog", name="Openway Assistant").is_visible()
    pg.get_by_label("Your question").fill("closest accessible restroom near uptown oxford")
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#ow-panel .ow-a .ow-main")
    # Show all on map filters the list and fits the map
    pg.locator("#ow-panel").get_by_role("button", name="Show all on map").click()
    pg.wait_for_selector("#assist-clear:not([hidden])")
    assert 1 < pg.evaluate("document.querySelectorAll('#list li').length") <= 6
    pg.locator("#assist-clear").click()
    assert pg.evaluate("document.querySelectorAll('#list li').length") > 6
    # Route here falls back to the saved route or Google Maps; Report opens the existing form, filled in
    pg.locator("#ow-panel").get_by_role("button", name="Report a problem").first.click()
    if pg.locator("#rp-text").count():
        assert "closest accessible restroom" in pg.locator("#rp-text").input_value()
        pg.keyboard.press("Escape")
    # Escape closes the panel and returns focus to the header button
    pg.locator("#ow-panel input[type=text]").focus()
    pg.keyboard.press("Escape")
    assert not pg.locator("#ow-panel").is_visible()
    assert pg.evaluate("document.activeElement.id") == "ask-open"
    assert not errs, errs
    ctx.close()
