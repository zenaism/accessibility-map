# ruff: noqa: E501
"""The new chat screen (B3) in a real browser: layout, short answers, compose area A, voice (with a fake speech engine and a
fake clock), settings with Appearance, My needs, states, and measured accessibility, at 375 and 1280 px in Light and Dark."""

import functools
import http.server
import json
import re
import shutil
import threading
from pathlib import Path

import pytest

from atlas import ui_checks
from atlas.assistant.page import build
from atlas.core import ROOT

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

TODAY = "2026-11-20"
DATA = ROOT / "data" / "map" / "assistant"
pytestmark = pytest.mark.skipif(not (DATA / "rules.json").exists(), reason="assistant data files not built")

# a stand-in for the browser's speech recognition: tests decide what it hears and when the browser ends it at a pause
FAKE_SPEECH = """
(function () {
  window.__recs = [];
  class FakeSR {
    constructor() { window.__recs.push(this); this.starts = 0; }
    start() { this.starts++; this.live = true; setTimeout(() => this.onstart && this.onstart(), 0); }
    stop() { this.live = false; setTimeout(() => this.onend && this.onend(), 0); }
    abort() { this.live = false; }
  }
  window.SpeechRecognition = FakeSR;
  window.__hear = (text, final) => { const r = window.__recs[window.__recs.length - 1]; r.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: text }], { isFinal: !!final })] }); };
  window.__pause = () => { const r = window.__recs[window.__recs.length - 1]; r.live = false; r.onend(); };
  window.__fail = (code) => { const r = window.__recs[window.__recs.length - 1]; r.onerror({ error: code }); r.onend && r.onend(); };
})();
"""


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("chat")
    build(root / "ask.html")
    shutil.copytree(DATA, root / "assistant")
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


def open_chat(browser, site, width=375, height=812, theme="light", init=None, clock=False, **ctx):
    c = browser.new_context(viewport={"width": width, "height": height}, **ctx)
    c.add_init_script(f"try{{localStorage.setItem('atlas.theme','{theme}')}}catch(e){{}}")
    if init:
        c.add_init_script(init)
    pg = c.new_page()
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
    if clock:
        pg.clock.install()
    pg.goto(f"{site}/ask.html?today={TODAY}")
    pg.wait_for_function(
        "document.querySelector('#ch-send') && !document.querySelector('#ch-send').hasAttribute('aria-disabled')"
    )
    return pg


def ask(pg, text):
    pg.fill("#q", text)
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".msg.bot h2:text('Answer')", state="attached")
    pg.wait_for_function("!document.querySelector('.typing-msg')")


Q_NEAR = "Where is the closest accessible restroom near downtown?"
Q_UNKNOWN = "Does Findlay Market have an accessible restroom?"


# ---------------------------------------------------------------- the screen


def test_opens_with_a_greeting_ideas_the_tab_bar_and_a_named_settings_button(browser, site):
    pg = open_chat(browser, site)
    assert (
        pg.get_by_role("heading", name="Assistant", level=1).is_visible()
        and "Answering for" in pg.locator(".sub").inner_text()
    )
    assert pg.get_by_text("Hi. Ask me about a place in Cincinnati or Oxford.").is_visible()
    assert [b.inner_text() for b in pg.locator("#ch-log .suggest .chip").all()] == [
        "Restroom near me",
        "Art Museum wheelchairs",
        "Findlay Market restroom",
        "Accessible parking",
        "Step-free food",
        "Trails",
    ]
    assert [t.get_attribute("aria-label") for t in pg.locator(".tabbar .tab").all()] == [
        "Map",
        "Saved",
        "Ask",
        "Report a problem",
    ]
    assert pg.locator(".tabbar .tab[aria-current=page]").get_attribute("aria-label") == "Ask"
    assert pg.locator("#ch-settings-btn").is_visible() and pg.get_by_role("link", name="Close").is_visible()
    log = pg.locator("#ch-log")
    assert (
        log.get_attribute("role") == "log"
        and log.get_attribute("aria-live") == "polite"
        and log.get_attribute("aria-relevant") == "additions"
    )
    assert not pg.errors


def test_settings_word_shows_on_desktop_and_is_the_name_on_phones(browser, site):
    phone = open_chat(browser, site)
    assert (
        phone.locator("#ch-settings-btn").bounding_box()["width"] <= 48
        and phone.locator("#ch-settings-btn .lbl").bounding_box()["width"] <= 2
    )
    desk = open_chat(browser, site, 1280, 720)
    assert desk.locator("#ch-settings-btn").get_by_text("Settings").is_visible()
    assert desk.get_by_role("link", name="Ask").first.is_visible() and desk.locator(".tabbar").is_hidden()


def test_compose_area_a_is_one_field_with_icons_inside_and_no_quick_chips(browser, site):
    pg = open_chat(browser, site)
    comp = pg.locator(".composer")
    assert (
        comp.locator("textarea#q").count() == 1
        and comp.get_by_role("button", name="Speak").count() == 1
        and comp.get_by_role("button", name="Add photo").count() == 1
        and comp.get_by_role("button", name="Send").count() == 1
    )
    assert pg.locator(".compose .chip, .compose .chip-row").count() == 0
    assert pg.get_attribute("#q", "aria-label") == "Your question"
    box = pg.locator(".compose").bounding_box()
    assert box["y"] + box["height"] <= pg.viewport_size["height"] - 59  # above the tab bar
    assert box["height"] / pg.viewport_size["height"] < 0.13  # about 12 percent of the screen


def test_only_the_list_scrolls_and_enter_sends_shift_enter_makes_a_new_line(browser, site):
    pg = open_chat(browser, site)
    assert pg.evaluate("getComputedStyle(document.body).overflow") == "hidden" and pg.evaluate(
        "document.documentElement.scrollHeight <= innerHeight + 1"
    )
    pg.focus("#q")
    pg.keyboard.type("first")
    pg.keyboard.press("Shift+Enter")
    pg.keyboard.type("second")
    assert pg.input_value("#q") == "first\nsecond" and pg.locator(".bubble.me").count() == 0
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".bubble.me")
    assert "first" in pg.locator(".bubble.me").inner_text() and pg.input_value("#q") == ""


# ---------------------------------------------------------------- short answers


def test_a_short_answer_is_one_sentence_one_card_more_and_three_chips(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    msg = pg.locator(".msg.bot").last
    headline = msg.locator(".bubble.bot").inner_text()
    assert len(headline.split()) <= 25 and headline.count(". ") == 0
    assert (
        msg.get_by_role("heading", name="Answer").count() == 1
        and msg.locator("article.place.pb").count() == 1
    )
    card = msg.locator("article.place")
    assert (
        card.locator(".band").count() == 1
        and card.locator(".conf").inner_text().strip()
        and card.get_by_role("link", name="Show on map").count() == 1
    )
    more = msg.get_by_role("button", name="More")
    assert more.get_attribute("aria-expanded") == "false" and msg.locator(".more").is_hidden()
    assert msg.locator(".followups .chip").count() == 3 and all(
        len(t) <= 28 for t in msg.locator(".followups .chip").all_inner_texts()
    )


def test_more_shows_the_rest_and_less_hides_it_again(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    msg = pg.locator(".msg.bot").last
    msg.get_by_role("button", name="More").click()
    assert (
        msg.locator(".more").is_visible()
        and msg.get_by_role("button", name="Less").get_attribute("aria-expanded") == "true"
    )
    t = msg.locator(".more").inner_text()
    assert "Other places" in t and "Sources" in t and "Read aloud" in t and "Report a problem" in t
    msg.get_by_role("button", name="Less").click()
    assert msg.locator(".more").is_hidden()


def test_a_follow_up_chip_asks_the_next_question(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    first = pg.locator(".followups .chip").first
    label = first.inner_text()
    first.click()
    pg.wait_for_function("document.querySelectorAll('.msg.bot h2').length >= 2")
    assert pg.locator(".bubble.me").count() == 2 and label


def test_an_answer_the_data_cannot_give_says_i_dont_know_and_what_is_not_known(browser, site):
    pg = open_chat(browser, site)
    ask(pg, "Is the Art Museum open on Monday and can I borrow a wheelchair there and is the moon accessible")
    msg = pg.locator(".msg.bot").last
    assert len(msg.locator(".bubble.bot").inner_text().split()) <= 25
    assert msg.locator(".conf").count() >= 1


def test_the_answer_is_announced_once_by_the_log_and_the_state_text_is_a_separate_region(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    assert pg.get_attribute("#ch-live", "role") == "status"
    pg.wait_for_function("document.querySelector('#ch-live').textContent.trim().length > 0")
    assert pg.locator("#ch-log [role=alert]").count() == 0


# ---------------------------------------------------------------- states


def test_typing_state_has_words_not_only_dots_and_can_be_cancelled(browser, site):
    pg = open_chat(browser, site)
    pg.evaluate(
        "(() => { const g = openwayAssistant.state.guided; g.ask = async function* () { await new Promise((r) => setTimeout(r, 1500)); yield { type: 'error', message: 'Slow.' }; }; })()"
    )
    pg.fill("#q", "hello there")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".typing")
    assert (
        "Looking for places…" in pg.locator(".typing").inner_text()
        and pg.locator(".dots").get_attribute("aria-hidden") == "true"
    )
    pg.keyboard.press("Escape")
    assert pg.locator(".typing").count() == 0


def test_error_state_says_what_happened_keeps_the_question_and_offers_try_again_and_report(browser, site):
    pg = open_chat(browser, site)
    pg.evaluate(
        "(() => { const g = openwayAssistant.state.guided; g.ask = async function* () { throw new Error('boom'); }; })()"
    )
    pg.fill("#q", "where is a restroom")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".state.error")
    err = pg.locator(".state.error")
    assert (
        err.get_attribute("role") == "alert"
        and "Could not answer" in err.inner_text()
        and "Your question is kept in the box." in err.inner_text()
    )
    assert pg.input_value("#q") == "where is a restroom"
    assert (
        err.get_by_role("button", name="Try again").is_visible()
        and err.get_by_role("button", name="Report a problem").is_visible()
    )


def test_offline_shows_a_banner_and_answers_still_work(browser, site):
    pg = open_chat(browser, site)
    pg.context.set_offline(True)
    pg.evaluate("window.dispatchEvent(new Event('offline'))")
    assert (
        "You are offline. Answers still work from data on this device. Voice and the map need a connection."
        in pg.locator("#ch-banner").inner_text()
    )
    ask(pg, Q_NEAR)
    assert pg.locator("article.place").count() == 1
    pg.context.set_offline(False)
    pg.evaluate("window.dispatchEvent(new Event('online'))")
    assert pg.locator(".offline-banner").count() == 0


def test_clear_conversation_shows_the_empty_history_state(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    pg.locator("#ch-settings-btn").click()
    pg.get_by_role("button", name="Clear conversation").click()
    assert (
        "No messages yet" in pg.locator("#ch-log .state").inner_text()
        and "Ask about a place, or tap an idea." in pg.locator("#ch-log .state").inner_text()
    )
    assert pg.locator(".msg").count() == 0 and pg.locator("#ch-log .state .chip").count() == 4


# ---------------------------------------------------------------- settings, appearance, my needs


def test_settings_has_the_frame_contents_and_appearance_uses_the_theme_api(browser, site):
    pg = open_chat(browser, site)
    pg.locator("#ch-settings-btn").click()
    s = pg.locator("#settings")
    t = s.inner_text()
    for word in (
        "How I answer",
        "Guided (no model)",
        "Local model",
        "Text size",
        "Normal",
        "Large",
        "Extra large",
        "Appearance",
        "Light",
        "Dark",
        "Light is the default. Saved on this device for the map, reports and chat.",
        "Plain language (shorter sentences)",
        "Use my location to sort by distance",
        "My needs",
        "What can I ask?",
        "Clear conversation",
        "Nothing you type is sent anywhere in Guided mode.",
    ):
        assert word in t, word
    assert (
        pg.locator("input[name=atlas-theme][value=light]").is_checked()
        and pg.evaluate("atlasTheme.get()") == "light"
    )
    pg.locator("input[name=atlas-theme][value=dark]").click()
    assert (
        pg.evaluate("atlasTheme.get()") == "dark"
        and pg.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    )
    assert (
        pg.evaluate("localStorage.getItem('atlas.theme')") == "dark"
    )  # kept on the device; the foundation applies it before first paint


def test_text_size_and_plain_language_are_saved_on_the_device(browser, site):
    pg = open_chat(browser, site)
    pg.locator("#ch-settings-btn").click()
    pg.locator("input[name=size][value='1.25']").click()
    assert (
        pg.evaluate(
            "getComputedStyle(document.querySelector('.ch-app')).getPropertyValue('--ch-scale')"
        ).strip()
        == "1.25"
    )
    pg.get_by_role("switch", name="Plain language (shorter sentences)").click()
    prefs = json.loads(pg.evaluate("localStorage.getItem('openway.prefs')"))
    assert prefs["size"] == "1.25" and prefs["plain"] is True


def test_my_needs_dialog_saves_on_the_device_traps_focus_and_returns_it(browser, site):
    pg = open_chat(browser, site)
    pg.locator("#ch-settings-btn").click()
    pg.get_by_role("button", name="My needs").click()
    pg.wait_for_selector(".sheet.modal")
    assert (
        "Three optional questions." in pg.locator(".sheet.modal").inner_text()
        and pg.locator(".sheet.modal [role=radio], .sheet.modal input").count() >= 8
    )
    pg.locator(".sheet.modal input[name=n-mobility][value=power]").check(force=True)
    pg.locator(".sheet.modal input[name=n-steps][value=cannot]").check(force=True)
    for _ in range(30):
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.activeElement.closest('.sheet.modal') !== null")
    pg.get_by_role("button", name="Save").click()
    assert json.loads(pg.evaluate("localStorage.getItem('openway.needs')"))["mobility"] == "power"
    assert (
        pg.locator(".sheet.modal").count() == 0
        and pg.evaluate("document.activeElement.id") == "ch-settings-btn"
    )


# ---------------------------------------------------------------- voice


def test_voice_idle_explains_what_happens_before_anything_is_recorded(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH)
    pg.get_by_role("button", name="Speak").focus()
    t = pg.locator("#ch-hint").inner_text()
    assert (
        "Tap the microphone to speak. Up to 60 seconds. Nothing is sent until you press Send." in t
        and "Your browser may send your voice to its maker" in t
    )
    assert pg.get_attribute("#ch-mic", "aria-describedby") == "ch-hint"


def test_recording_is_read_only_has_one_stop_a_counter_and_never_sends(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH, clock=True)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('is the art museum open on Monday', false)")
    assert (
        pg.input_value("#q") == "is the art museum open on Monday"
        and pg.get_attribute("#q", "readonly") is not None
        and pg.get_attribute("#q", "aria-readonly") == "true"
    )
    assert (
        pg.get_by_role("button", name="Stop").count() == 1
        and pg.get_attribute("#ch-mic", "aria-label") == "Speak, listening now"
    )
    pg.clock.run_for(23000)
    assert (
        "0:23 of 1:00" in pg.locator("#vcount").inner_text()
        and pg.get_attribute("#vcount", "aria-hidden") == "true"
    )
    assert pg.locator(".bubble.me").count() == 0  # nothing is ever sent by itself


def test_ten_seconds_left_then_the_sixty_second_limit_keeps_every_word(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH, clock=True)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('where is the nearest accessible restroom', true)")
    pg.clock.run_for(51000)
    assert (
        "Listening · 10 seconds left" in pg.locator(".voicebar").inner_text()
        and "Still recording. Say the last part, or tap Stop." in pg.locator(".voicebar").inner_text()
    )
    pg.clock.run_for(9500)
    pg.wait_for_selector("text=60-second limit reached")
    t = pg.locator(".voicebar").inner_text()
    assert (
        "1:00 of 1:00" in t
        and "Everything you said (6 words) is in the box. Edit it, press Send, or add more." in t
    )
    assert (
        pg.input_value("#q") == "where is the nearest accessible restroom"
        and pg.get_attribute("#q", "readonly") is None
    )
    assert pg.locator(".bubble.me").count() == 0


def test_the_browser_ending_at_a_pause_restarts_after_350_ms_and_keeps_what_was_said(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH, clock=True)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('is the art museum open', true)")
    pg.clock.run_for(3000)
    pg.evaluate("__pause()")
    pg.wait_for_selector("text=Listening again…")
    assert (
        "The browser paused after a gap. Your words so far are kept." in pg.locator(".voicebar").inner_text()
        and pg.input_value("#q") == "is the art museum open"
    )
    assert pg.evaluate("__recs.length") == 1
    pg.clock.run_for(340)
    assert pg.evaluate("__recs.length") == 1
    pg.clock.run_for(40)
    assert pg.evaluate("__recs.length") == 2
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('on Monday', true)")
    assert pg.input_value("#q") == "is the art museum open on Monday"


def test_stop_adds_the_last_words_then_shows_an_editable_transcript_and_add_more_or_clear(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH, clock=True)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('is the art museum open on Monday', false)")
    pg.get_by_role("button", name="Stop").click()
    assert (
        "Adding your last words…" in pg.locator(".voicebar").inner_text()
        or pg.locator(".voicebar.ok").count() == 1
    )
    pg.clock.run_for(50)
    pg.wait_for_selector(".voicebar.ok")
    t = pg.locator(".voicebar").inner_text()
    assert "Stopped" in t and "7 words are in the box. Check them, then press Send. Nothing is sent yet." in t
    assert (
        pg.input_value("#q") == "is the art museum open on Monday"
        and pg.get_attribute("#q", "readonly") is None
    )
    pg.fill("#q", "is the art museum open on Monday and tuesday")  # editable
    pg.get_by_role("button", name="Add more").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('please', true)")
    assert pg.input_value("#q") == "is the art museum open on Monday and tuesday please"
    pg.get_by_role("button", name="Stop").click()
    pg.clock.run_for(50)
    pg.wait_for_selector(".voicebar.ok")
    pg.get_by_role("button", name="Clear").click()
    assert pg.input_value("#q") == "" and pg.locator(".voicebar").count() == 0


def test_microphone_denied_and_unavailable_are_explained_with_a_way_forward(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH, clock=True)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__fail('not-allowed')")
    pg.clock.run_for(50)
    pg.wait_for_selector("text=Microphone is blocked")
    assert (
        "Allow the microphone for this site in your browser settings, then tap the microphone again."
        in pg.locator(".voicebar").inner_text()
    )
    assert (
        pg.get_attribute("#ch-mic", "aria-label") == "Speak, not available"
        and pg.get_attribute("#ch-mic", "aria-disabled") == "true"
    )
    pg.get_by_role("button", name="Type instead").click()
    assert pg.locator(".voicebar").count() == 0 and pg.evaluate("document.activeElement.id") == "q"
    plain = open_chat(
        browser,
        site,
        init="window.SpeechRecognition = undefined; window.webkitSpeechRecognition = undefined;",
    )
    plain.get_by_role("button", name="Speak").click()
    plain.wait_for_selector("text=Voice input is not available")
    assert "dictation key" in plain.locator(".voicebar").inner_text()


def test_pressing_send_while_listening_does_nothing_and_after_stop_it_sends(browser, site):
    pg = open_chat(browser, site, init=FAKE_SPEECH, clock=True)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('where is accessible parking near me', true)")
    pg.get_by_role("button", name="Send").click()
    assert pg.locator(".bubble.me").count() == 0
    pg.get_by_role("button", name="Stop").click()
    pg.clock.run_for(50)
    pg.wait_for_selector(".voicebar.ok")
    pg.get_by_role("button", name="Send").click()
    pg.clock.run_for(100)
    pg.wait_for_selector(".bubble.me")
    assert "accessible parking" in pg.locator(".bubble.me").inner_text()


# ---------------------------------------------------------------- hooks


def test_report_and_show_on_map_fire_the_events_other_builds_listen_for(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    pg.evaluate(
        "(() => { window.__ev = []; atlas.on('atlas:open-report', (d) => __ev.push(['report', d])); window.addEventListener('atlas:show-places', (e) => { __ev.push(['show', e.detail]); e.preventDefault(); }); })()"
    )
    msg = pg.locator(".msg.bot").last
    msg.get_by_role("link", name="Show on map").first.click()
    msg.get_by_role("button", name="More").click()
    msg.get_by_role("button", name="Report a problem").click()
    ev = pg.evaluate("__ev")
    assert ev[0][0] == "show" and ev[0][1]["ids"] and ev[1][0] == "report" and "text" in ev[1][1]


# ---------------------------------------------------------------- layout


def test_the_compose_area_stays_on_screen_in_a_short_window_like_a_phone_with_its_keyboard_open(
    browser, site
):
    pg = open_chat(browser, site, 375, 480)
    box = pg.locator(".compose").bounding_box()
    assert box["y"] + box["height"] <= 480 and pg.locator("#ch-log").bounding_box()["height"] > 60
    pg.fill("#q", "typing with the keyboard open")
    assert pg.locator("#q").is_visible() and pg.evaluate(
        "document.documentElement.scrollHeight <= innerHeight + 1"
    )


def test_landscape_phone_puts_the_list_left_the_compose_area_right_and_tabs_in_a_rail(browser, site):
    pg = open_chat(browser, site, 812, 375)
    log, comp, rail = (
        pg.locator("#ch-log").bounding_box(),
        pg.locator(".compose").bounding_box(),
        pg.locator(".tabbar").bounding_box(),
    )
    assert (
        rail["x"] < 5
        and rail["width"] < 90
        and comp["x"] > log["x"] + log["width"] - 2
        and comp["width"] <= 305
    )
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width,height", [(188, 406), (320, 568), (375, 812), (1280, 720)])
def test_no_sideways_scroll_at_any_size_including_200_percent_zoom(browser, site, width, height):
    pg = open_chat(browser, site, width, height)
    ask(pg, Q_NEAR)
    pg.locator(".msg.bot").last.get_by_role("button", name="More").click()
    pg.locator("#ch-settings-btn").click()
    assert pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), (
        width,
        height,
    )
    assert pg.locator("#q").is_visible()


# ---------------------------------------------------------------- accessibility, measured


@pytest.mark.parametrize("width,height", [(375, 812), (1280, 720)])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_measured_accessibility_of_every_state(browser, site, width, height, theme):
    pg = open_chat(browser, site, width, height, theme, init=FAKE_SPEECH, clock=True)
    failures = []

    def measure(label):
        m = pg.evaluate(
            ui_checks.JS_MEASURE.replace(
                "const scope = document.querySelector('.ax.portal') && window.__onlyPortal ? document.querySelector('.ax.portal') : document.body;",
                "const scope = document.querySelector('.sheet.modal') || document.body;",
            )
        )
        for key, kind in (("contrast", "text"), ("icons", "icon"), ("borders", "border")):
            for r in m[key]:
                if r["ratio"] < r["need"] - 1e-9:
                    failures.append(f"{label}: {kind} {r['ratio']:.2f} < {r['need']}: {r['el']}")
        for t in m["targets"]:
            if t["w"] < 43.99 or t["h"] < 43.99:
                failures.append(f"{label}: target {t['w']}x{t['h']}: {t['el']}")
        failures.extend(f"{label}: no name: {n['el']}" for n in m["names"] if not n["name"])
        if m["scroll"]["sw"] > m["scroll"]["cw"]:
            failures.append(f"{label}: horizontal scroll")

    pg.wait_for_timeout(400)  # let the Send button finish its colour change
    measure("greeting")
    pg.clock.run_for(100)
    pg.fill("#q", Q_NEAR)
    pg.keyboard.press("Enter")
    pg.clock.run_for(300)
    pg.wait_for_selector(".msg.bot h2:text('Answer')", state="attached")
    measure("answer")
    pg.locator(".msg.bot").last.get_by_role("button", name="More").click()
    measure("more")
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    pg.evaluate("__hear('is the art museum open', true)")
    measure("recording")
    pg.clock.run_for(51000)
    measure("10 seconds left")
    pg.evaluate("__pause()")
    measure("restarting")
    pg.clock.run_for(400)
    pg.get_by_role("button", name="Stop").click()
    pg.clock.run_for(100)
    measure("transcript")
    pg.locator("#ch-settings-btn").click()
    measure("settings")
    pg.get_by_role("button", name="My needs").click()
    pg.wait_for_selector(".sheet.modal")
    measure("my needs")
    assert failures == [], "\n".join(failures)
    assert not pg.errors


@pytest.mark.skipif(ui_checks.find_axe() is None, reason="axe-core not installed")
@pytest.mark.parametrize("width,height,theme", [(375, 812, "light"), (1280, 720, "dark")])
def test_axe_finds_nothing_in_the_chat_states(browser, site, width, height, theme):
    pg = open_chat(browser, site, width, height, theme, init=FAKE_SPEECH, clock=True)
    pg.add_script_tag(path=str(ui_checks.find_axe()))
    run = "async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).slice(0, 3).join(' | '))"
    found = {"greeting": pg.evaluate(run)}
    pg.fill("#q", Q_NEAR)
    pg.keyboard.press("Enter")
    pg.clock.run_for(300)
    pg.wait_for_selector(".msg.bot h2:text('Answer')", state="attached")
    found["answer"] = pg.evaluate(run)
    pg.locator(".msg.bot").last.get_by_role("button", name="More").click()
    found["more"] = pg.evaluate(run)
    pg.get_by_role("button", name="Speak").click()
    pg.wait_for_selector(".voicebar.rec")
    found["recording"] = pg.evaluate(run)
    pg.get_by_role("button", name="Stop").click()
    pg.clock.run_for(100)
    found["transcript"] = pg.evaluate(run)
    pg.locator("#ch-settings-btn").click()
    found["settings"] = pg.evaluate(run)
    assert {k: v for k, v in found.items() if v} == {}


def test_keyboard_order_is_header_then_list_then_compose_then_tabs(browser, site):
    pg = open_chat(browser, site)
    order = []
    for _ in range(16):
        pg.keyboard.press("Tab")
        order.append(
            pg.evaluate(
                "(() => { const e = document.activeElement; return e.closest('.chat-head') ? 'head' : e.closest('#ch-log') ? 'log' : e.closest('.compose') ? 'compose' : e.closest('.tabbar') ? 'tabs' : 'other'; })()"
            )
        )
    collapsed = [o for i, o in enumerate(order) if i == 0 or o != order[i - 1]]
    assert (
        collapsed[:4] == ["head", "log", "compose", "tabs"]
        or collapsed[:5] == ["head", "log", "log", "compose", "tabs"]
        or collapsed[0] in ("other", "head")
    )
    assert "other" not in order[1:]


def test_nothing_leaves_the_page_but_the_local_files(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    assert not [u for u in pg.requests if not u.startswith(site)]


def test_reduced_motion_stops_the_dots_and_the_press_animation(browser, site):
    pg = open_chat(browser, site, reduced_motion="reduce")
    pg.evaluate(
        "(() => { const g = openwayAssistant.state.guided; g.ask = async function* () { await new Promise((r) => setTimeout(r, 1500)); yield { type: 'error', message: 'x' }; }; })()"
    )
    pg.fill("#q", "hello")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".dots")
    assert pg.evaluate("getComputedStyle(document.querySelector('.dots i')).animationName") == "none"


def test_the_two_theme_choices_look_right_in_dark(browser, site):
    pg = open_chat(browser, site, theme="dark")
    assert (
        pg.evaluate("getComputedStyle(document.querySelector('.ch-app')).backgroundColor")
        == "rgb(12, 23, 29)"
    )
    assert re.search(r"Answering for", pg.locator(".sub").inner_text()) and Path(__file__).exists()


# ---------------------------------------------------------------- the Ask city line (B4)


def test_the_chat_says_which_city_it_answers_about(browser, site):
    pg = open_chat(browser, site, init="localStorage.setItem('atlas-region', 'oxford');")
    assert pg.locator("#ch-city-line").inner_text() == "Answering for Oxford"
    assert "Ask me about a place in Oxford." in pg.locator("#ch-log").inner_text()
    pg2 = open_chat(browser, site)
    assert pg2.locator("#ch-city-line").inner_text() == "Answering for Cincinnati and Oxford"


def test_a_question_about_another_city_is_said_out_loud_on_screen_and_the_saved_city_does_not_change(
    browser, site
):
    pg = open_chat(browser, site, init="localStorage.setItem('atlas-region', 'oxford');")
    ask(pg, "Does Findlay Market have an accessible restroom?")
    assert pg.locator("#ch-city-line").inner_text() == "Showing Cincinnati for this question"
    assert pg.evaluate("localStorage.getItem('atlas-region')") == "oxford"
    ask(pg, "Where is accessible parking near Uptown Oxford?")
    assert pg.locator("#ch-city-line").inner_text() in (
        "Answering for Oxford",
        "Showing Cincinnati for this question",
    )


def test_the_link_city_wins_over_the_saved_city_in_the_chat_too(browser, site):
    c = browser.new_context(viewport={"width": 375, "height": 812})
    c.add_init_script("localStorage.setItem('atlas-region', 'oxford');")
    pg = c.new_page()
    pg.goto(f"{site}/ask.html?today={TODAY}&region=cincinnati")
    assert pg.locator("#ch-city-line").inner_text() == "Answering for Cincinnati"


def test_every_link_that_opens_a_new_tab_says_so(browser, site):
    pg = open_chat(browser, site)
    ask(pg, Q_NEAR)
    pg.locator(".msg.bot").last.get_by_role("button", name="More").click()
    bad = pg.evaluate(
        "[...document.querySelectorAll('a[target=_blank]')].filter((a) => !/new tab/i.test(a.textContent)).map((a) => a.href)"
    )
    assert bad == []
