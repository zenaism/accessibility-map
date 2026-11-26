# ruff: noqa: E501
"""The shared visual foundation of the Accessibility Map (session B0, style A Harbor).

One module that returns everything a page generator needs to look and behave like the chosen design:

    css()            fonts + Harbor tokens (light and dark) + component classes, all scoped under ".ax"
    sprite()         the Lucide icon sprite (<svg> with <symbol id="lucide-NAME">)
    theme_boot_js()  tiny script for <head>: sets data-theme before first paint, defines window.atlasTheme
    js()             events (atlas:open-report ...), toast, bottom sheet, switches, radios
    head_snippet()   what to put in <head> (meta + theme boot)
    body_snippet()   what to put at the start of <body> (the sprite) and, before </body>, js()

and small HTML builders (button, chip, rating_badge, place_card, tabbar, topbar ...). The names, the event contracts
and who owns which file are in docs/ui_components.md. Everything is self-hosted: Figtree (SIL OFL) and Lucide (ISC)
files live in src/atlas/web/foundation/ with their licences; no request leaves the page.

Nothing here restyles an existing screen: every rule needs a parent with class "ax".
"""

from __future__ import annotations

import base64
import re
from html import escape
from pathlib import Path

FOUNDATION = Path(__file__).with_name("web") / "foundation"
FONT_WEIGHTS = (400, 600, 700)

# rating key -> (icon id, word). The word is always shown with the symbol; colour is never the only signal.
RATINGS = {
    "yes": ("yes", "Accessible"),
    "partial": ("partial", "Partly accessible"),
    "no": ("no", "Not accessible"),
    "unknown": ("unknown", "Not known"),
}


def _read(name: str) -> str:
    return (FOUNDATION / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------- assets


def font_face_css(base_url: str | None = None) -> str:
    """@font-face rules for Figtree 400, 600 and 700. With base_url=None the files are inlined (base64), so a page
    is one file and works offline; with a base_url ("fonts/") the page links the .woff2 files copied there."""
    out = []
    for w in FONT_WEIGHTS:
        if base_url is None:
            raw = (FOUNDATION / "fonts" / f"figtree-{w}.woff2").read_bytes()
            src = "data:font/woff2;base64," + base64.b64encode(raw).decode()
        else:
            src = f"{base_url.rstrip('/')}/figtree-{w}.woff2"
        out.append(
            f"@font-face{{font-family:'Figtree';font-weight:{w};font-style:normal;font-display:swap;"
            f"src:url({src}) format('woff2')}}"
        )
    return "\n".join(out)


def css(font_base_url: str | None = None) -> str:
    return font_face_css(font_base_url) + "\n" + _read("harbor.css")


def icon_names() -> list[str]:
    return sorted(p.stem for p in (FOUNDATION / "icons").glob("*.svg"))


def sprite() -> str:
    """Hidden SVG sprite. Use an icon with <svg class="ic" aria-hidden="true"><use href="#lucide-NAME"/></svg>."""
    symbols = []
    for name in icon_names():
        text = (FOUNDATION / "icons" / f"{name}.svg").read_text(encoding="utf-8")
        inner = re.search(r"<svg[^>]*>(.*)</svg>", text, re.S).group(1).strip()
        symbols.append(f'<symbol id="lucide-{name}" viewBox="0 0 24 24">{inner}</symbol>')
    return (
        '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>'
        + "".join(symbols)
        + "</defs></svg>"
    )


def theme_boot_js() -> str:
    return _read("theme-boot.js")


def js() -> str:
    """The shared runtime (events, toast, sheet, switches). Needs theme_boot_js() to have run in <head>."""
    return _read("foundation.js")


def licences() -> dict[str, str]:
    return {"Figtree (SIL OFL 1.1)": _read("fonts/OFL.txt"), "Lucide icons (ISC)": _read("icons/LICENSE.txt")}


FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0B6E75" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 '
    '4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 '
    '3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/></svg>'
)
# The tab icon is the same map mark as the logo in the app bar (icons/map.svg), in the brand teal.
FAVICON_LINK = '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,' + FAVICON_SVG.replace("#", "%23").replace('"', "'") + '">\n'


def head_snippet() -> str:
    """Put inside <head>: tells the browser the page has both schemes, sets data-theme before first paint."""
    return (
        FAVICON_LINK
        + '<meta name="color-scheme" content="light dark">\n'
        '<meta name="theme-color" content="#FFFFFF">\n'
        "<script>" + theme_boot_js() + "</script>"
    )


def body_snippet() -> str:
    """Put right after <body> (the icon sprite); add <script>js()</script> before </body>."""
    return sprite()


# ---------------------------------------------------------------- builders (return HTML strings)


def _e(s: object) -> str:
    return escape(str(s), quote=True)


def _attrs(attrs: dict[str, object] | None) -> str:
    out = []
    for k, v in (attrs or {}).items():
        if v is None or v is False:
            continue
        out.append(f" {_e(k.replace('_', '-'))}" if v is True else f' {_e(k.replace("_", "-"))}="{_e(v)}"')
    return "".join(out)


def icon(name: str, cls: str = "") -> str:
    c = f"ic {cls}".strip()
    return f'<svg class="{c}" aria-hidden="true" focusable="false"><use href="#lucide-{_e(name)}"/></svg>'


def theme_toggle(**attrs: object) -> str:
    """The Light/Dark switch: a sliding toggle with a sun on the left and a moon on the right (on = Dark). It is a
    native button with role="switch" named "Dark theme"; foundation.js wires it to window.atlasTheme and keeps
    aria-checked in step with the theme, whichever control changed it."""
    a = {
        "class": "theme-toggle",
        "role": "switch",
        "aria-checked": "false",
        "aria-label": "Dark theme",
        "data-theme-toggle": "",
        **attrs,
    }
    return (
        f'<button type="button"{_attrs(a)}><span class="ts-track">{icon("sun", "ts-sun")}{icon("moon", "ts-moon")}'
        '<span class="ts-knob"></span></span></button>'
    )


def button(
    label: str,
    kind: str = "secondary",
    icon_name: str | None = None,
    *,
    icon_only: bool = False,
    block: bool = False,
    href: str | None = None,
    disabled: bool = False,
    busy: bool = False,
    emit: str | None = None,
    place_id: str | None = None,
    region: str | None = None,
    **attrs: object,
) -> str:
    """kind: primary | secondary | ghost | danger. icon_only: the label becomes the accessible name (aria-label).
    emit: an atlas event name; the click fires it with place_id and region (see docs/ui_components.md)."""
    cls = f"btn btn-{kind}" + (" btn-icon" if icon_only else "") + (" block" if block else "")
    a = {
        "class": cls,
        "aria-label": label if icon_only else None,
        "data-atlas-emit": emit,
        "data-place-id": place_id,
        "data-region": region,
        "aria-busy": "true" if busy else None,
        **attrs,
    }
    inner = icon(icon_name, "spin" if busy else "") if icon_name else ""
    if not icon_only:
        inner += f"<span>{_e(label)}</span>"
    if href is not None:
        return f"<a{_attrs({**a, 'href': href})}>{inner}</a>"
    a["type"] = "button"
    a["disabled"] = disabled
    return f"<button{_attrs(a)}>{inner}</button>"


def chip(label: str, pressed: bool = False, icon_name: str | None = None) -> str:
    return (
        f'<button type="button" class="chip" aria-pressed="{str(pressed).lower()}">'
        + icon("check", "tick")
        + (icon(icon_name) if icon_name else "")
        + f"<span>{_e(label)}</span></button>"
    )


def chip_row(chips: list[str], label: str) -> str:
    return f'<div class="chip-row" role="group" aria-label="{_e(label)}">' + "".join(chips) + "</div>"


def search_field(
    placeholder: str = "Search places", value: str = "", *, id: str = "q", label: str | None = None
) -> str:
    lab = label or placeholder
    clear = button("Clear search", "ghost", "close", icon_only=True) if value else ""
    return (
        f'<div class="search" role="search" aria-label="{_e(lab)}">'
        + icon("search")
        + f'<input type="search" id="{_e(id)}" value="{_e(value)}" placeholder="{_e(placeholder)}" aria-label="{_e(lab)}">'
        + clear
        + "</div>"
    )


def text_field(
    label: str,
    *,
    id: str,
    value: str = "",
    hint: str = "",
    error: str = "",
    multiline: bool = False,
    placeholder: str = "",
) -> str:
    """A labelled text field. An error is linked with aria-describedby and marked aria-invalid."""
    desc = []
    if hint:
        desc.append(f"{id}-hint")
    if error:
        desc.append(f"{id}-err")
    common = {
        "id": id,
        "aria-invalid": "true" if error else None,
        "aria-describedby": " ".join(desc) or None,
        "placeholder": placeholder or None,
    }
    control = (
        f'<textarea class="textarea"{_attrs(common)}>{_e(value)}</textarea>'
        if multiline
        else f'<input class="input" type="text"{_attrs({**common, "value": value})}>'
    )
    return (
        '<div class="field">'
        + f'<label for="{_e(id)}">{_e(label)}</label>'
        + (f'<span class="hint" id="{_e(id)}-hint">{_e(hint)}</span>' if hint else "")
        + control
        + (f'<p class="err" id="{_e(id)}-err">{icon("alert")}<span>{_e(error)}</span></p>' if error else "")
        + "</div>"
    )


def toggle(label: str, checked: bool = False, *, id: str) -> str:
    """A switch (role=switch). foundation.js flips aria-checked and fires an "atlas:switch" event on the element."""
    return (
        f'<div class="sw-row"><span id="{_e(id)}-l">{_e(label)}</span>'
        f'<button type="button" class="toggle" role="switch" aria-checked="{str(checked).lower()}" aria-labelledby="{_e(id)}-l">'
        f'<span class="track"><span class="knob">{icon("check")}</span></span></button></div>'
    )


def radio_group(label: str, options: list[tuple[str, str]], value: str, *, id: str) -> str:
    """Big choice buttons (role=radiogroup, arrow keys move). options: [(value, text)]."""
    items = "".join(
        f'<button type="button" class="choice" role="radio" data-value="{_e(v)}" aria-checked="{str(v == value).lower()}" '
        f'tabindex="{0 if v == value else -1}"><span>{_e(t)}</span><span class="mark">{icon("check")}</span></button>'
        for v, t in options
    )
    return (
        f'<div class="stack"><span class="lbl" id="{_e(id)}-l">{_e(label)}</span>'
        f'<div class="stack" role="radiogroup" aria-labelledby="{_e(id)}-l">{items}</div></div>'
    )


def appearance_group(current: str = "light") -> str:
    """Settings row "Appearance: Light / Dark": native radios named atlas-theme; foundation.js applies the choice
    through window.atlasTheme and keeps the radios in step with it."""
    opts = (("light", "Light", "sun"), ("dark", "Dark", "moon"))
    items = "".join(
        f'<label><input type="radio" name="atlas-theme" value="{v}"{" checked" if v == current else ""}>'
        f'<span class="o">{icon("check", "tick")}{icon(i)}{t}</span></label>'
        for v, t, i in opts
    )
    return (
        '<fieldset class="group"><legend>Appearance</legend>'
        f'<div class="seg">{items}</div>'
        '<p class="hint small">Light is the default. Saved on this device.</p></fieldset>'
    )


def star_rating(name: str = "stars", value: int = 0) -> str:
    """1 to 5 stars as native radios (keyboard: arrow keys). Each star has its number as visible text."""
    items = "".join(
        f'<label class="star"><input type="radio" name="{_e(name)}" value="{n}" aria-label="{n} of 5"{" checked" if n == value else ""}>'
        f'{icon("star")}<span class="n" aria-hidden="true">{n}</span></label>'
        for n in range(1, 6)
    )
    return f'<fieldset class="group"><legend>Rate how accessible it is</legend><div class="stars">{items}</div></fieldset>'


def rating_badge(
    rating: str, *, large: bool = False, reported: bool = False, label: str | None = None
) -> str:
    """Word + symbol, never colour alone. Partly accessible gets a ring in the badge text colour (one ring colour)."""
    ic, word = RATINGS.get(rating, RATINGS["unknown"])
    key = rating if rating in RATINGS else "unknown"
    cls = f"badge {key}" + (" lg" if large else "") + (" reported" if reported else "")
    return f'<span class="{cls}">{icon(ic)}<span>{_e(label or word)}</span></span>'


def place_card(
    name: str,
    rating: str,
    facts: list[tuple[str, str, str]],
    source: str,
    *,
    place_id: str,
    region: str,
    saved: bool = False,
    heading_level: int = 2,
) -> str:
    """Place card, variant B (rating first). facts: [(icon, label, value)]. The Report button fires atlas:open-report."""
    ic, _ = RATINGS.get(rating, RATINGS["unknown"])
    key = rating if rating in RATINGS else "unknown"
    stats = "".join(
        f'<div class="stat">{icon(i)}<span class="k">{_e(k)}</span><span class="v">{_e(v)}</span></div>'
        for i, k, v in facts
    )
    h = f"h{heading_level}"
    return (
        f'<article class="place card" aria-label="{_e(name)}">'
        f'<div style="display:flex;gap:12px;align-items:center"><span class="ratetile {key}">{icon(ic)}</span>'
        f'<div style="display:grid;gap:6px;min-width:0"><{h} class="name">{_e(name)}</{h}>{rating_badge(rating)}</div></div>'
        f'<div class="stat3">{stats}</div>'
        f'<p class="conf">{icon("clock")}<span>{_e(source)}</span></p>'
        + button("Route here", "primary", "route", block=True)
        + '<div class="rowbtns" style="display:grid;grid-template-columns:1fr 1fr">'
        + button("Saved" if saved else "Save", "secondary", "save")
        + button("More details", "secondary", "info")
        + "</div>"
        + button(
            "Report a problem", "ghost", "report", emit="atlas:open-report", place_id=place_id, region=region
        )
        + "</article>"
    )


def sheet(title: str, body_html: str, *, id: str, grab: bool = True) -> str:
    """Static (docked) bottom sheet markup. For a modal sheet with focus trap use atlas.ui.sheet.open() in JS."""
    return (
        f'<section class="sheet" aria-labelledby="{_e(id)}">'
        + ('<div class="grab"></div>' if grab else "")
        + f'<h2 class="name" id="{_e(id)}">{_e(title)}</h2>{body_html}</section>'
    )


def banner(text: str, kind: str = "warn", icon_name: str | None = None, action: str | None = None) -> str:
    """kind: warn (amber) | info (teal). role=status, so a screen reader hears it when it appears."""
    ic = icon_name or ("alert" if kind == "warn" else "check")
    return (
        f'<div class="banner{" info" if kind == "info" else ""}" role="status">{icon(ic)}<span>{_e(text)}</span>'
        + (button(action, "secondary") if action else "")
        + "</div>"
    )


def toast(text: str, action: str | None = None) -> str:
    """Static markup of a toast (for pages that render their own). At run time use atlas.ui.toast()."""
    return (
        f'<div class="toast" role="status"><span>{_e(text)}</span>'
        + (f'<button type="button" class="btn">{_e(action)}</button>' if action else "")
        + "</div>"
    )


def state(
    title: str, text: str, icon_name: str = "ask", *, error: bool = False, action_html: str = ""
) -> str:
    """Empty state (default) or error state (error=True, red border; role=alert)."""
    return (
        f'<div class="state{" error" if error else ""}"{" role=alert" if error else ""}>'
        f'<span class="big">{icon("alert" if error and icon_name == "ask" else icon_name)}</span>'
        f'<p class="lead">{_e(title)}</p><p class="muted">{_e(text)}</p>{action_html}</div>'
    )


TABS = (
    ("map", "Map", "map"),
    ("saved", "Saved", "save"),
    ("ask", "Ask", "ask"),
    ("report", "Report", "report"),
)
TAB_EVENTS = {"saved": "atlas:open-saved", "ask": "atlas:open-ask", "report": "atlas:open-report"}


def tabbar(active: str = "map", hrefs: dict[str, str] | None = None) -> str:
    """The four-item phone tab bar: Map, Saved, Ask, Report (flag icon). Saved, Ask and Report fire their atlas events;
    when nothing listens the plain href is followed, so a page works before the other builds land."""
    hrefs = hrefs or {}
    items = []
    for key, text, ic in TABS:
        name = "Report a problem" if key == "report" else text
        a = {
            "class": "tab",
            "href": hrefs.get(key, "#"),
            "aria-label": name,
            "aria-current": "page" if key == active else None,
            "data-tab": key,
            "data-atlas-emit": TAB_EVENTS.get(key),
        }
        items.append(f"<a{_attrs(a)}>{icon(ic)}<span>{text}</span></a>")
    return f'<nav class="tabbar four" aria-label="Main">{"".join(items)}</nav>'


def topbar(
    active: str = "map",
    hrefs: dict[str, str] | None = None,
    brand: str = "Accessibility Map",
    *,
    settings: bool = True,
) -> str:
    """Desktop top bar: brand, Map, Saved, the Light/Dark toggle, Settings (only where the page has settings),
    Report a problem (secondary), Ask (the one filled button)."""
    hrefs = hrefs or {}

    def link(key: str, text: str, ic: str, kind: str, emit: str | None = None) -> str:
        a = {
            "class": f"btn btn-{kind}",
            "href": hrefs.get(key, "#"),
            "aria-current": "page" if key == active else None,
            "data-tab": key,
            "data-atlas-emit": emit,
        }
        return f"<a{_attrs(a)}>{icon(ic)}<span>{_e(text)}</span></a>"

    return (
        f'<header class="appbar top"><span class="brand">{icon("map")}{_e(brand)}</span>'
        '<nav class="nav-links" aria-label="Main">'
        + link("map", "Map", "map", "ghost")
        + link("saved", "Saved", "save", "ghost", "atlas:open-saved")
        + theme_toggle()
        + (link("settings", "Settings", "settings", "ghost") if settings else "")
        + link("report", "Report a problem", "report", "secondary", "atlas:open-report")
        + link("ask", "Ask", "ask", "primary", "atlas:open-ask")
        + "</nav></header>"
    )


def page(
    title: str, body_html: str, *, theme_class: str = "ax", extra_css: str = "", extra_js: str = ""
) -> str:
    """A complete standalone page with the foundation in it (used by the components test page)."""
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        f"<title>{_e(title)}</title>\n{head_snippet()}\n<style>\n{css()}\n"
        f"html,body{{margin:0}}body{{background:var(--bg,#F3F7F8)}}\n{extra_css}</style></head>"
        f'<body class="{theme_class}">{body_snippet()}\n{body_html}\n<script>{js()}</script>'
        + (f"<script>{extra_js}</script>" if extra_js else "")
        + "</body></html>"
    )
