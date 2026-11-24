# ruff: noqa: E501
"""The shared UI foundation (B0): static checks on the assets and the builders, then a real browser (Playwright +
Chromium) for the theme, the events, the sheet and the measured accessibility of the components page."""

import functools
import http.server
import re
import threading

import pytest

from atlas import ui_components_page
from atlas import ui_foundation as u

# ---------------------------------------------------------------- static


def test_assets_are_self_hosted_and_licensed():
    for w in u.FONT_WEIGHTS:
        assert (u.FOUNDATION / "fonts" / f"figtree-{w}.woff2").stat().st_size > 5000
    lic = u.licences()
    assert "SIL OPEN FONT LICENSE" in lic["Figtree (SIL OFL 1.1)"].upper()
    assert "ISC" in lic["Lucide icons (ISC)"]


def test_no_external_urls_in_the_foundation():
    blob = u.css() + u.sprite() + u.js() + u.theme_boot_js() + u.head_snippet()
    urls = [x for x in re.findall(r"https?://[^\s'\")]+", blob) if "www.w3.org" not in x]
    assert urls == []
    assert "@import" not in blob


def test_sprite_has_every_icon_the_frames_use():
    need = [
        "ask",
        "near",
        "search",
        "save",
        "route",
        "report",
        "settings",
        "mic",
        "stop",
        "send",
        "more",
        "close",
        "back",
        "share",
        "camera",
        "filter",
        "pin",
        "info",
        "star",
        "sun",
        "moon",
        "copy",
        "yes",
        "partial",
        "no",
        "unknown",
        "map",
        "alert",
        "check",
        "clock",
        "door",
        "down",
        "image",
        "list",
        "offline",
        "parking",
        "plus",
        "right",
        "spinner",
        "toilet",
        "trash",
    ]
    have = set(u.icon_names())
    assert not (set(need) - have)
    sp = u.sprite()
    for n in need:
        assert f'id="lucide-{n}"' in sp


def test_dark_tokens_override_but_map_colours_are_fixed():
    c = u.css()
    light, dark = c.split('html[data-theme="dark"]')[0], c.split('html[data-theme="dark"]')[1].split("}")[0]
    assert "--bg: #F3F7F8" in light and "--bg: #0C171D" in dark
    for fixed in ("--map-bg", "--pin-yes", "--pin-partial", "--user-dot", "--route", "--pin-edge"):
        assert fixed in light and fixed not in dark


def test_every_rule_is_scoped_under_ax():
    css = u._read("harbor.css")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@media[^{]*\{", "{", css)
    for sel in re.findall(r"(?:^|\})\s*([^{}@]+)\{", css):
        for part in sel.split(","):
            part = part.strip()
            if part and not part.startswith(("from", "to", "50%")):
                assert ".ax" in part, part


def test_partial_ring_uses_the_badge_text_colour_only():
    css = u._read("harbor.css")
    assert re.search(r"\.ax \.badge\.partial \{ border-width: 2px; border-color: currentColor;", css)
    assert "partial-ring" not in css


def test_tabbar_has_four_items_with_flag_and_events():
    h = u.tabbar("saved")
    assert h.count('class="tab"') == 4
    assert [m for m in re.findall(r"<span>(\w+)</span>", h)] == ["Map", "Saved", "Ask", "Report"]
    assert "#lucide-report" in h and 'aria-label="Report a problem"' in h
    assert h.count('aria-current="page"') == 1 and 'data-tab="saved"' in h
    assert 'data-atlas-emit="atlas:open-report"' in h


def test_builders_escape_and_name_icon_only_buttons():
    assert 'aria-label="Close"' in u.button("Close", "ghost", "close", icon_only=True)
    assert "&lt;b&gt;" in u.text_field("<b>", id="x")
    card = u.place_card(
        "A&B", "partial", [("door", "Entrance", "Step-free")], "src", place_id="p1", region="oxford"
    )
    assert (
        "A&amp;B" in card and 'data-atlas-emit="atlas:open-report"' in card and 'data-place-id="p1"' in card
    )


# ---------------------------------------------------------------- browser

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from atlas import ui_checks  # noqa: E402


@pytest.fixture(scope="module")
def base():
    out = ui_components_page.build()
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out.parent))
    h.log_message = lambda *a, **k: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}/components.html"
    s.shutdown()
    s.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def fresh(browser, base, scheme="dark", init=None, width=375):
    ctx = browser.new_context(viewport={"width": width, "height": 800}, color_scheme=scheme)
    if init:
        ctx.add_init_script(init)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(base)
    return ctx, pg


def test_default_is_light_even_when_the_device_is_dark(browser, base):
    ctx, pg = fresh(browser, base, "dark")
    assert pg.evaluate("atlasTheme.get()") == "light"
    assert pg.evaluate("window.__themeAtBodyStart") == "light"
    assert (
        pg.evaluate("getComputedStyle(document.querySelector('.ax')).getPropertyValue('--bg').trim()")
        == "#F3F7F8"
    )
    ctx.close()


def test_choice_is_stored_applied_before_paint_and_announced(browser, base):
    ctx, pg = fresh(browser, base)
    pg.evaluate(
        "window.__seen = []; document.addEventListener('atlas:theme-changed', e => __seen.push(e.detail.theme))"
    )
    assert pg.evaluate("atlasTheme.set('dark')") == "dark"
    assert pg.evaluate("localStorage.getItem('atlas.theme')") == "dark"
    assert pg.evaluate("__seen") == ["dark"]
    assert (
        pg.evaluate("getComputedStyle(document.querySelector('.ax')).getPropertyValue('--bg').trim()")
        == "#0C171D"
    )
    assert pg.evaluate("document.querySelector('input[name=atlas-theme][value=dark]').checked")
    pg.reload()
    assert pg.evaluate("window.__themeAtBodyStart") == "dark"  # set in <head>, so no flash
    assert pg.evaluate("atlasTheme.set('junk')") == "light"  # anything else means Light
    assert not pg.errors
    ctx.close()


def test_appearance_radio_switches_theme(browser, base):
    ctx, pg = fresh(browser, base)
    pg.locator("input[name=atlas-theme][value=dark]").click()
    assert pg.evaluate("atlasTheme.get()") == "dark"
    ctx.close()


def test_theme_works_when_storage_is_blocked(browser, base):
    blocked = "Object.defineProperty(window, 'localStorage', {get(){ throw new Error('blocked'); }});"
    ctx, pg = fresh(browser, base, init=blocked)
    assert pg.evaluate("atlasTheme.get()") == "light"
    assert pg.evaluate("atlasTheme.set('dark')") == "dark"
    assert pg.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    assert not pg.errors
    ctx.close()


def test_map_colours_do_not_change_in_dark(browser, base):
    ctx, pg = fresh(browser, base)
    q = "['--map-bg','--pin-yes','--pin-partial','--user-dot','--route'].map(k => getComputedStyle(document.querySelector('.ax')).getPropertyValue(k).trim()).join()"
    light = pg.evaluate(q)
    pg.evaluate("atlasTheme.set('dark')")
    assert pg.evaluate(q) == light
    ctx.close()


def test_partial_ring_colour_equals_badge_text_colour(browser, base):
    ctx, pg = fresh(browser, base)
    for theme in ("light", "dark"):
        pg.evaluate(f"atlasTheme.set('{theme}')")
        same = pg.evaluate(
            "(() => { const b = document.querySelector('.badge.partial'); const c = getComputedStyle(b); return c.borderTopColor === c.color && parseFloat(c.borderTopWidth) >= 2 && c.borderTopStyle === 'solid'; })()"
        )
        assert same, theme
    ctx.close()


def test_events_and_fallback(browser, base):
    ctx = browser.new_context(viewport={"width": 375, "height": 800})
    pg = ctx.new_page()
    pg.set_content(u.page("Bare", u.tabbar("map", {"saved": "#saved"})))
    # nobody listens yet: emit returns 0, never throws, and the link keeps its href
    assert pg.evaluate("atlas.emit('atlas:open-saved', {})") == 0
    assert pg.evaluate("atlas.emit('atlas:open-report', {placeId: 'p'})") == 0
    assert pg.evaluate("document.querySelector('.tabbar a[data-tab=saved]').getAttribute('href')") == "#saved"
    assert (
        pg.evaluate(
            "(() => { const e = new MouseEvent('click', {bubbles: true, cancelable: true}); document.querySelector('.tabbar a[data-tab=saved]').dispatchEvent(e); return e.defaultPrevented; })()"
        )
        is False
    )
    pg.evaluate("(() => { atlas.on('atlas:open-saved', () => {}); })()")
    assert (
        pg.evaluate(
            "(() => { const e = new MouseEvent('click', {bubbles: true, cancelable: true}); document.querySelector('.tabbar a[data-tab=saved]').dispatchEvent(e); return e.defaultPrevented; })()"
        )
        is True
    )
    ctx.close()
    ctx, pg = fresh(browser, base)
    pg.evaluate("(() => { window.__got = []; atlas.on('atlas:open-report', (d) => __got.push(d)); })()")
    pg.get_by_role("button", name="Fire open-report").click()
    assert pg.evaluate("__got") == [{"placeId": "demo-1", "region": "oxford"}]
    pg.get_by_role("link", name="Report a problem").click()
    assert pg.evaluate("__got.length") == 2 and pg.evaluate("__got[1]") == {}
    assert pg.evaluate("atlas.emit('atlas:open-ask', {placeId: 'x'})") == 1  # the demo page logs it
    with pytest.raises(Exception, match="atlas events start with atlas:"):
        pg.evaluate("atlas.emit('open-report')")
    ctx.close()


def test_sheet_traps_focus_makes_background_inert_and_returns_focus(browser, base):
    ctx, pg = fresh(browser, base)
    opener = pg.get_by_role("button", name="Open a sheet")
    opener.click()
    pg.wait_for_selector("[role=dialog][aria-modal=true]")
    assert pg.evaluate("document.activeElement.closest('[role=dialog]') !== null")
    assert pg.evaluate("document.querySelector('main').closest('[inert]') !== null")
    for _ in range(10):
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.activeElement.closest('[role=dialog]') !== null")
    for _ in range(10):
        pg.keyboard.press("Shift+Tab")
        assert pg.evaluate("document.activeElement.closest('[role=dialog]') !== null")
    pg.keyboard.press("Escape")
    assert pg.locator("[role=dialog]").count() == 0
    assert pg.evaluate("document.querySelector('[inert]')") is None
    assert pg.evaluate("document.activeElement.id") == "demo-sheet"
    ctx.close()


def test_switch_and_radio_keyboard(browser, base):
    ctx, pg = fresh(browser, base)
    sw = pg.get_by_role("switch", name="Plain language")
    assert sw.get_attribute("aria-checked") == "false"
    sw.focus()
    pg.keyboard.press("Space")
    assert sw.get_attribute("aria-checked") == "true"
    pg.get_by_role("radio", name="Oxford").first.focus()
    pg.keyboard.press("ArrowDown")
    assert pg.get_by_role("radio", name="Dayton (limited data)").get_attribute("aria-checked") == "true"
    ctx.close()


def test_toast_is_announced_and_goes_away(browser, base):
    ctx, pg = fresh(browser, base)
    pg.get_by_role("button", name="Show a toast").click()
    assert pg.locator(".toasts[aria-live=polite] .toast").count() == 1
    pg.get_by_role("button", name="Undo").last.click()
    assert pg.locator(".toasts .toast").count() == 0
    ctx.close()


def test_measured_accessibility_375_and_1280_light_and_dark(browser):
    r = ui_checks.run(browser=browser)
    assert len(r["views"]) == 4
    assert r["failures"] == [], "\n" + ui_checks.report(r)
    for v in r["views"]:
        assert (
            v["min_target"] >= 44
            and v["min_text"] >= 4.5
            and v["min_icon"] >= 3
            and v["min_border"] >= 3
            and v["min_focus"] >= 3
        )
        assert v["requests"] == 1  # the page itself, from the local test server
