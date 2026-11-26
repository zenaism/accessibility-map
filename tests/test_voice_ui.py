"""Spoken route directions in the real map page (Chromium, fake speech, simulated position).
The natural voice (Kokoro, about 92 MB) is only loaded in the one test that needs it."""

# ruff: noqa: F811
import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest

from .test_map_app import GRAPH, _data, browser, cdn, map_app, open_first, open_map, search  # noqa: F401  (fixtures)

TTS = Path(__file__).resolve().parents[1] / "data" / "map" / "tts"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Like the map tests' site, plus the tts/ folder (the natural voice files) next to the page."""
    root = tmp_path_factory.mktemp("site")
    (root / "oxford.html").write_text(map_app.render(_data(), "Oxford"))
    (root / "routing").mkdir()
    shutil.copy(GRAPH, root / "routing" / "oxford.graph.json")
    if TTS.exists():
        (root / "tts").symlink_to(TTS, target_is_directory=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


pytestmark = pytest.mark.skipif(not GRAPH.exists(), reason="walking graph not exported")

FAKE_SPEECH = """
window.__said = [];
(function(){
  function U(t){ this.text = t; }
  Object.defineProperty(window, 'SpeechSynthesisUtterance', { value: U, configurable: true });
  Object.defineProperty(window, 'speechSynthesis', { value: { speak: function(u){ window.__said.push(u.text); }, cancel: function(){}, getVoices: function(){ return [{name:'Samantha', lang:'en-US', localService:true}]; } }, configurable: true });
})();
"""


def said(pg):
    return [t for t in pg.evaluate("window.__said") if t.strip()]


def start_route(pg, voice_on):
    search(pg)
    open_first(pg)
    pg.get_by_role("button", name="Route here").click()
    pg.wait_for_selector("[data-nav=start]")
    if voice_on:
        pg.get_by_role("switch", name="Voice off").click()
        assert pg.get_by_role("switch", name="Voice on").get_attribute("aria-checked") == "true"
    model = pg.evaluate("AtlasNav.N.model")
    line = model["line"]
    pg.context.set_geolocation({"latitude": line[0][1], "longitude": line[0][0], "accuracy": 8})
    pg.locator("[data-nav=start]").click()
    pg.wait_for_selector(".stepcard")
    return model, line


def test_voice_is_off_by_default_and_says_nothing(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    start_route(pg, voice_on=False)
    pg.wait_for_timeout(400)
    assert said(pg) == []
    assert pg.get_by_role("switch", name="Voice off").get_attribute("aria-checked") == "false"
    assert not pg.errors


def test_voice_on_reads_the_first_step_then_the_next_one_when_close(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    model, line = start_route(pg, voice_on=True)
    pg.wait_for_function("window.__said.some(t => t.startsWith('Route started. '))")
    first = said(pg)
    assert first[0] == "Voice on."
    assert "Finding you." in first
    # walk to a point inside the second step: the app says that step, and a heads-up when it is near its end
    steps = model["steps"]
    k = steps[1]["fromIdx"]
    pg.context.set_geolocation({"latitude": line[k + 1][1], "longitude": line[k + 1][0], "accuracy": 8})
    pg.wait_for_function("AtlasNav.N.auto === 1")
    # a spoken step never contains brackets or semicolons
    assert not any("(" in t or ";" in t for t in said(pg))
    assert not pg.errors


def test_heads_up_with_the_distance_first(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    model, line = start_route(pg, voice_on=True)
    pg.wait_for_function("window.__said.some(t => t.startsWith('Route started. '))")
    # stand about 60 feet before the end of step 1: the next step is announced as "In N feet, ..."
    end = line[model["steps"][0]["toIdx"]]
    pg.context.set_geolocation({"latitude": end[1] - 0.00005, "longitude": end[0], "accuracy": 8})
    pg.wait_for_function("window.__said.some(t => /In \\d+ feet, /.test(t))", timeout=8000)
    assert not pg.errors


def test_repeat_and_speed(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    start_route(pg, voice_on=False)
    pg.get_by_role("button", name="Repeat").click()  # works even with Voice off: the person asked for it
    assert said(pg)[-1].startswith("Route started") or said(pg)[-1].startswith("Head")
    pg.get_by_text("Voice settings").click()
    pg.get_by_role("radio", name="Fast").click()
    assert pg.get_by_role("radio", name="Fast").get_attribute("aria-checked") == "true"
    assert pg.evaluate("JSON.parse(localStorage.getItem('atlas.voice')).speed") == "fast"
    assert pg.locator("details#voiceset").get_attribute("open") is not None  # stays open across redraws


def test_natural_voice_that_cannot_load_falls_back_to_the_device_voice(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    pg.context.route("**/tts/kokoro-worker.js", lambda r: r.fulfill(status=404, body="no"))
    start_route(pg, voice_on=True)
    pg.get_by_text("Voice settings").click()
    pg.get_by_role("switch", name="Natural voice").click()
    pg.wait_for_selector("text=The natural voice did not load")
    pg.get_by_role("button", name="Repeat").click()
    assert said(pg)[-1]  # the device voice spoke
    assert pg.get_by_role("switch", name="Natural voice").get_attribute("aria-checked") == "false"


def test_requests_stay_on_this_site_while_the_voice_is_used(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    start_route(pg, voice_on=True)
    assert not [r for r in pg.requests if "127.0.0.1" not in r and "nationalmap" not in r]


@pytest.mark.skipif(not (TTS / "kokoro-worker.js").exists(), reason="no natural voice files")
def test_natural_voice_loads_from_this_site_and_speaks(browser, cdn, site):
    pg = open_map(browser, cdn, site, init=FAKE_SPEECH)
    start_route(pg, voice_on=True)
    pg.get_by_text("Voice settings").click()
    pg.get_by_role("switch", name="Natural voice").click()
    pg.wait_for_selector("text=Natural voice is ready", timeout=120000)
    before = len(said(pg))
    pg.get_by_role("button", name="Repeat").click()
    pg.wait_for_function("AtlasNav.VOICE.state.speaking === true", timeout=60000)
    assert len(said(pg)) == before  # spoken by the natural voice, not the device voice
    assert not [r for r in pg.requests if "127.0.0.1" not in r and "nationalmap" not in r]
