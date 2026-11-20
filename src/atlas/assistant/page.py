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


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Openway Assistant</title>
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


def build(out: Path | None = None) -> Path:
    out = out or ROOT / "data/map/ask.html"
    out.write_text(PAGE.replace("__CSS__", css()).replace("__JS__", js_bundle()))
    return out


def build_standalone(out: Path | None = None) -> Path:
    """One file with the data inside: opens from an email attachment, a shared drive or any static host, no server.
    Guided mode only (the local model needs the server)."""
    import json

    out = out or ROOT / "data/map/ask-standalone.html"
    d = ROOT / "data/map/assistant"
    data = {k: json.loads((d / f"{k}.json").read_text()) for k in ("rules", "cincinnati", "oxford")}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = PAGE.replace("__CSS__", css()).replace(
        "__JS__", "window.__OPENWAY_DATA = " + blob + ";\n" + js_bundle()
    )
    out.write_text(html)
    return out


if __name__ == "__main__":
    for p in (build(), build_standalone()):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size // 1024} KB")
