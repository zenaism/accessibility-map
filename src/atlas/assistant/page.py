# ruff: noqa: E501
"""Builds data/map/ask.html: the Openway Assistant as its own page (one self-contained file: the page, the
styles and the JavaScript; the data files are loaded from assistant/ next to it).

    python -m atlas.assistant.page
"""

from __future__ import annotations

from pathlib import Path

from ..core import ROOT

WEB = Path(__file__).resolve().parents[1] / "web" / "assistant"
SCRIPTS = ["text", "dates", "tools", "planner", "composer", "verify", "engine", "voice", "photo", "chat"]


def js_bundle() -> str:
    return "\n".join((WEB / f"{n}.js").read_text() for n in SCRIPTS)


def css() -> str:
    return (WEB / "assistant.css").read_text()


CHAT = Path(__file__).resolve().parents[1] / "web" / "chat"
# modules of the new chat screen: the engine and answer pieces from web/assistant, then speech in and the screen itself
# the route voice (Kokoro natural voice or the device voice): Read aloud in the chat uses the same engine
MAP_VOICE = WEB.parent / "map" / "voice.js"
APP_SCRIPTS = [
    WEB / f"{n}.js"
    for n in ("text", "dates", "tools", "planner", "composer", "verify", "engine", "voice", "photo")
] + [MAP_VOICE, CHAT / "speech.js", CHAT / "chat.js"]
VOLUME = '<symbol id="lucide-volume" viewBox="0 0 24 24"><path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/></symbol>'
MAP_HREF = "index.html"
REPORT_FALLBACK = "#report"  # the Report tab fires atlas:open-report; no GitHub link any more


def _ratecfg() -> dict | None:
    from ..map_viewer import ratings_config

    return ratings_config()


def _regions_json() -> str:
    """The visible cities (short names and tiers) so the chat can say which city it answers about."""
    import json

    from .. import regions

    keep = ("id", "short", "tier")
    return json.dumps([{k: r[k] for k in keep} for r in regions.catalog()]).replace("</", "<\\/")


def _chat_parts(ui, embedded: bool = False) -> tuple[str, str]:
    """The chat header and the compose area (the chosen design). embedded=True is the copy inside the map window:
    its Close is a plain button (the map closes the panel) and its question box has its own id, because the map has a #q."""
    qid = "ch-q" if embedded else "q"
    settings = (
        '<button type="button" class="btn btn-secondary btn-icon withlabel" id="ch-settings-btn" aria-expanded="false" aria-controls="settings">'
        + ui.icon("settings")
        + '<span class="vh lbl">Settings</span></button>'
    )
    head = (
        '<header class="chat-head"><div class="titles"><h1>Assistant</h1>'
        '<p class="sub"><span class="vh" id="ch-mode">Guided mode</span><span id="ch-city-line">Answering for Cincinnati and Oxford</span></p></div>'
        + ui.theme_toggle(id="ch-theme-toggle")
        + settings
        + ui.button(
            "Close", "ghost", "close", icon_only=True, href=None if embedded else MAP_HREF, id="ch-close"
        )
        + "</header>"
    )
    compose = (
        '<form class="compose cv-a" id="ch-form" aria-label="Ask a question" novalidate>'
        '<div id="ch-voice"></div><div id="ch-attach" hidden></div>'
        '<div class="composer"><textarea id="'
        + qid
        + '" rows="1" aria-label="Your question" placeholder="Ask about a place" enterkeyhint="send" autocomplete="off"></textarea>'
        + ui.button(
            "Speak",
            "ghost",
            "mic",
            icon_only=True,
            id="ch-mic",
            **{"class": "btn btn-ghost btn-icon mic", "aria-pressed": "false"},
        ).replace('<span class="vh">', '<span class="vh">')
        + ui.button("Add photo", "ghost", "camera", icon_only=True, id="ch-photo")
        + ui.button(
            "Send", "primary", "send", icon_only=True, id="ch-send", **{"class": "btn btn-icon btn-send"}
        ).replace('type="button"', 'type="submit"', 1)
        + '</div><p class="hint small" id="ch-hint" role="status" hidden></p><input type="file" accept="image/*" id="ch-file" class="vh" tabindex="-1" aria-hidden="true"></form>'
    )
    return head, compose


def embed() -> dict[str, str]:
    """The chat inside the map window (no page of its own): {"html", "css", "js"}.
    Same header, conversation and compose area as the Ask page. It has no top bar and no tab bar, so there is no Ask button
    in it: the map opens it and its Close button gives the window back. The map calls Openway.chat.mount on the first open."""
    from .. import ui_foundation as ui

    head, compose = _chat_parts(ui, embedded=True)
    head = (
        head.replace('<header class="chat-head">', '<div class="chat-head">')
        .replace("</header>", "</div>")
        .replace("<h1>Assistant</h1>", "<h2>Assistant</h2>")
    )
    html = (
        '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>'
        + VOLUME
        + "</defs></svg>"
        '<section class="ch-app ch-embed" id="chat-dock" aria-label="Assistant" hidden>'
        '<div class="ch-col">'
        + head
        + '<section class="settings" id="settings" aria-label="Settings" hidden></section>'
        '<div class="mw"><div id="ch-banner"></div><div class="log" id="ch-log" role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversation" tabindex="0"></div></div>'
        + compose
        + '</div><div class="vh" id="ch-live" role="status" aria-live="polite" aria-atomic="true"></div></section>'
    )
    scripts = "\n".join(p.read_text() for p in APP_SCRIPTS if p != MAP_VOICE)  # the map page already has the route voice
    return {
        "html": html,
        "css": (CHAT / "chat.css").read_text() + "\n" + (CHAT / "embed.css").read_text(),
        "js": scripts,
    }


def app_html(inline: str = "") -> str:
    """The new chat screen: header, settings, conversation, compose area A, voice bar, tab bar (Ask active)."""
    from .. import report_form
    from .. import ui_foundation as ui

    hrefs = {"map": MAP_HREF, "saved": MAP_HREF + "#saved", "report": REPORT_FALLBACK, "ask": "ask.html"}
    # one banner landmark only: the chat header below is the banner, so the top bar keeps its navigation but not its <header>
    top = (
        ui.topbar("ask", hrefs)
        .replace('<header class="appbar top">', '<div class="appbar top">')
        .replace("</header>", "</div>")
        .replace('<span class="brand">', '<span class="brand" aria-hidden="true">')
        .replace(
            '<a class="btn btn-ghost" href="#" data-tab="settings">',
            '<a class="btn btn-ghost" href="#" id="settings-desk" data-tab="settings" role="button">',
        )
    )
    head, compose = _chat_parts(ui)
    body = (
        '<a class="skip" href="#q">Skip to the question box</a>'
        '<div class="ch-app">'
        f'<div class="only-desktop" data-rp-inert>{top}</div>'
        '<div class="ch-col" data-rp-inert>'
        + head
        + '<section class="settings" id="settings" aria-label="Settings" hidden></section>'
        '<main class="mw" id="main"><div id="ch-banner"></div><div class="log" id="ch-log" role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversation" tabindex="0"></div></main>'
        + compose
        + "</div>"
        f'<div class="only-phone">{ui.tabbar("ask", hrefs)}</div>'
        '<div class="vh" id="ch-live" role="status" aria-live="polite" aria-atomic="true"></div></div>'
    )
    scripts = "\n".join(p.read_text() for p in APP_SCRIPTS)
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><title>Accessibility Map</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">'
        '<meta name="description" content="Ask about accessible places, restrooms, parking, food, events and trails in Cincinnati and Oxford. Answers come with sources and dates.">\n'
        + ui.head_snippet()
        + f"\n<style>\n{ui.css()}\n{(CHAT / 'chat.css').read_text()}\n{report_form.css()}\n</style></head>"
        + f'<body class="ax chatapp">{ui.body_snippet().replace("</defs>", VOLUME + "</defs>")}\n{body}\n'
        f"<script>{ui.js()}</script>\n<script>window.__REGIONS={_regions_json()};{inline}\n{scripts}\n"
        f"{report_form.config_js(_ratecfg())}\n"
        "window.atlasRegion=function(){var a=window.openwayAssistant;return (a&&a.state.region)||((window.__REGIONS||[])[0]||{}).id||null;};\n"
        f"{report_form.js()}\n"
        "(function () { var root = document.querySelector('.ch-app'); var api = Openway.chat.mount(root, {base: 'assistant/'}); window.openwayAssistant = api;\n"
        "  var d = document.getElementById('settings-desk'); if (d) d.addEventListener('click', function (e) { e.preventDefault(); document.getElementById('ch-settings-btn').click(); }); })();</script></body></html>"
    )


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Accessibility Map</title>
<link rel="icon" type="image/svg+xml" href="__ICON__">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Ask about accessible places, restrooms, parking, food, events and trails in Cincinnati and Oxford. Answers come with sources and dates.">
<meta name="theme-color" content="#ffffff">
<style>
:root{--ink:#111827;--muted:#4b5563;--line:#d9dde3;--soft:#f3f4f6;--focus:#2563eb}
*{box-sizing:border-box}html,body{height:100%;margin:0}body{background:#fff;color:var(--ink);overflow:hidden}
.skip{position:absolute;left:12px;top:-80px;background:#fff;padding:10px 14px;border-radius:10px;z-index:4000;box-shadow:0 2px 12px rgba(0,0,0,.2);font-weight:600;color:var(--ink)}
.skip:focus{top:10px}
main{height:100%}
__CSS__
</style></head><body>
<nav aria-label="Skip link"><a class="skip" href="#ow-skip">Skip to the question box</a></nav>
<main id="ow-root" aria-label="Openway Assistant"></main>
<noscript><p style="padding:1em">The Openway Assistant needs JavaScript. You can still use the <a href="cincinnati.html">Cincinnati map</a> or the <a href="oxford.html">Oxford map</a>, which list every place as text.</p></noscript>
<script>
__JS__
(function () {
  var root = document.getElementById('ow-root');
  var api = Openway.chat.mount(root, {mode: 'page', base: 'assistant/', inputId: 'ow-skip'});
  document.querySelector('.skip').addEventListener('click', function (e) { e.preventDefault(); api.focus(); });
  window.openwayAssistant = api;
})();
</script></body></html>
"""


def build(out: Path | None = None, legacy: bool = False) -> Path:
    """data/map/ask.html. The default is the new chat screen (B3, on the B0 foundation); legacy=True builds the old page."""
    from ..ui_foundation import FAVICON

    out = out or ROOT / "data/map/ask.html"
    out.write_text(PAGE.replace("__ICON__", FAVICON).replace("__CSS__", css()).replace("__JS__", js_bundle()) if legacy else app_html())
    return out


def build_standalone(out: Path | None = None, legacy: bool = False) -> Path:
    """One file with the data inside: opens from an email attachment, a shared drive or any static host, no server.
    Guided mode only (the local model needs the server)."""
    import json

    from ..ui_foundation import FAVICON

    out = out or ROOT / "data/map/ask-standalone.html"
    d = ROOT / "data/map/assistant"
    data = {k: json.loads((d / f"{k}.json").read_text()) for k in ("rules", "cincinnati", "oxford")}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    if legacy:
        html = PAGE.replace("__ICON__", FAVICON).replace("__CSS__", css()).replace(
            "__JS__", "window.__OPENWAY_DATA = " + blob + ";\n" + js_bundle()
        )
    else:
        html = app_html("window.__OPENWAY_DATA = " + blob + ";")
    out.write_text(html)
    return out


if __name__ == "__main__":  # builds the new chat screen; use build(legacy=True) for the old page
    for p in (build(), build_standalone()):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size // 1024} KB")
