# ruff: noqa: E501
"""The components test page (generated, never shipped to users): every foundation component in every state.

    python scripts/build_ui_components.py            -> build/ui_components/components.html

Open it at 375 px and at 1280 px, in Light and in Dark (the Appearance control on the page switches theme through
window.atlasTheme, the same call the app uses). atlas.ui_checks measures it.
"""

from __future__ import annotations

from pathlib import Path

from . import ui_foundation as u

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "ui_components" / "components.html"

FACTS = [
    ("door", "Entrance", "Step-free"),
    ("toilet", "Restroom", "Not known"),
    ("parking", "Parking", "2 reserved"),
]


def section(title: str, body: str, id: str) -> str:
    return f'<section class="stack3" aria-labelledby="{id}"><h2 class="h2" id="{id}">{title}</h2>{body}</section>'


def sample(label: str, html: str) -> str:
    return f'<div class="stack"><p class="small muted">{label}</p>{html}</div>'


def map_sample() -> str:
    pins = "".join(
        f'<div class="pin {k}{" sel" if sel else ""}" style="left:{x}px;top:{y}px">{u.icon(ic)}</div>'
        for k, ic, x, y, sel in (
            ("yes", "yes", 40, 40, True),
            ("partial", "partial", 100, 90, False),
            ("no", "no", 160, 40, False),
            ("unknown", "unknown", 220, 90, False),
        )
    )
    svg = (
        '<svg viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">'
        '<rect width="300" height="150" fill="var(--map-road)"/><rect x="10" y="10" width="80" height="50" rx="6" fill="var(--map-block)"/>'
        '<rect x="110" y="70" width="90" height="60" rx="6" fill="var(--map-block)"/>'
        '<path class="routecase" d="M30 130 L120 120 L170 60 L260 50"/><path class="routeline" d="M30 130 L120 120 L170 60 L260 50"/></svg>'
    )
    you = '<div class="you" style="left:30px;top:130px"><div class="ring"></div><div class="dot"></div></div>'
    return (
        '<div role="img" aria-label="Sample map: four pins, a route and the location dot. The map stays light in dark mode." '
        f'style="position:relative;height:150px;border-radius:var(--r-card);overflow:hidden;border:1px solid var(--line);background:var(--map-bg)"><div class="mapbg">{svg}</div>{pins}{you}</div>'
    )


def build_body() -> str:
    b = u.button
    parts = []
    parts.append(
        section(
            "Appearance and events",
            u.appearance_group()
            + '<div class="rowbtns">'
            + b("Show a toast", "secondary", "info", id="demo-toast")
            + b("Open a sheet", "secondary", "filter", id="demo-sheet")
            + b(
                "Fire open-report",
                "secondary",
                "report",
                emit="atlas:open-report",
                place_id="demo-1",
                region="oxford",
                id="demo-emit",
            )
            + "</div>"
            '<p class="small muted" id="event-log" role="status">No event yet.</p>',
            "s-theme",
        )
    )
    parts.append(
        section(
            "Buttons",
            sample(
                "Primary, secondary, ghost, danger",
                '<div class="rowbtns">'
                + b("Route here", "primary", "route")
                + b("Save", "secondary", "save")
                + b("More", "ghost", "info")
                + b("Delete", "danger", "trash")
                + "</div>",
            )
            + sample(
                "Icon only (round and square)",
                '<div class="rowbtns">'
                + b("Settings", "ghost", "settings", icon_only=True)
                + b("Close", "secondary", "close", icon_only=True)
                + b("Send", "primary", "send", icon_only=True, **{"class": "btn btn-primary btn-icon round"})
                + b("Microphone", "secondary", "mic", icon_only=True)
                + b("Stop", "danger", "stop", icon_only=True)
                + b("Copy link", "secondary", "share", icon_only=True)
                + b("Take a photo", "secondary", "camera", icon_only=True)
                + b("More options", "ghost", "dots", icon_only=True)
                + "</div>",
            )
            + sample(
                "Disabled, busy, keyboard focus",
                '<div class="rowbtns">'
                + b("Send report", "primary", "send", disabled=True)
                + b("Sending", "primary", "spinner", busy=True)
                + b(
                    "Focused",
                    "secondary",
                    "map-pin" if False else "pin",
                    **{"class": "btn btn-secondary force-focus"},
                )
                + "</div>",
            )
            + sample("Full width", b("Send rating", "primary", "send", block=True)),
            "s-buttons",
        )
    )
    parts.append(
        section(
            "Chips",
            u.chip_row(
                [
                    u.chip("Restrooms", True, "toilet"),
                    u.chip("Parking", False, "parking"),
                    u.chip("Open now"),
                    u.chip("Blocked", True),
                    u.chip("Broken lift"),
                ],
                "Filter places",
            ),
            "s-chips",
        )
    )
    parts.append(
        section(
            "Fields",
            sample(
                "Search, empty and with text",
                u.search_field("Search places", id="q1")
                + u.search_field(
                    "Search places", "Maple Street Library", id="q2", label="Search places, with text"
                ),
            )
            + u.text_field("Place name", id="f1", hint="As it appears on the sign", value="Corner Cafe")
            + u.text_field("What is wrong", id="f2", multiline=True, hint="Optional", placeholder="Type here")
            + u.text_field("Where", id="f3", error="Choose a place before sending", value=""),
            "s-fields",
        )
    )
    parts.append(
        section(
            "Switch, radio group, stars",
            u.toggle("Plain language", False, id="sw1")
            + u.toggle("Use my location", True, id="sw2")
            + u.radio_group(
                "City",
                [("cincinnati", "Cincinnati"), ("oxford", "Oxford"), ("dayton", "Dayton (limited data)")],
                "oxford",
                id="rg1",
            )
            + u.star_rating("stars", 3),
            "s-choice",
        )
    )
    parts.append(
        section(
            "Rating badges",
            '<div class="rowbtns">'
            + u.rating_badge("yes")
            + u.rating_badge("partial")
            + u.rating_badge("no")
            + u.rating_badge("unknown")
            + u.rating_badge("partial", reported=True, label="Partly accessible, reported")
            + "</div>"
            '<div class="rowbtns">'
            + u.rating_badge("yes", large=True)
            + u.rating_badge("partial", large=True)
            + "</div>",
            "s-badges",
        )
    )
    parts.append(
        section(
            "Place card",
            u.place_card(
                "Maple Street Library",
                "yes",
                FACTS,
                "Library website, Mar 2026",
                place_id="demo-1",
                region="oxford",
            )
            + u.place_card(
                "Corner Cafe",
                "partial",
                FACTS,
                "Reported by 2 visitors, Oct 2026",
                place_id="demo-2",
                region="oxford",
                saved=True,
            )
            + u.place_card(
                "Old Mill Hall",
                "unknown",
                [
                    ("door", "Entrance", "Not known"),
                    ("toilet", "Restroom", "Not known"),
                    ("parking", "Parking", "Not known"),
                ],
                "No data yet",
                place_id="demo-3",
                region="oxford",
            ),
            "s-card",
        )
    )
    parts.append(
        section(
            "Banner, toast, states",
            u.banner("Safari may clear saved places after 7 days away.", "warn", action="Copy link")
            + u.banner("Restored 4 places. 1 is no longer in the data.", "info")
            + u.banner("You are offline. Answers still work from data on this device.", "warn", "offline")
            + u.toast("Removed Corner Cafe", "Undo")
            + u.state("No saved places yet", "Tap the heart on a place to keep it here.", "save")
            + u.state(
                "Could not load places",
                "Check your connection and try again.",
                "alert",
                error=True,
                action_html=b("Try again", "secondary", "route"),
            )
            + sample(
                "Docked bottom sheet",
                u.sheet(
                    "Choose a city",
                    u.radio_group(
                        "City", [("cincinnati", "Cincinnati"), ("oxford", "Oxford")], "cincinnati", id="rg2"
                    ),
                    id="sh1",
                ),
            ),
            "s-states",
        )
    )
    parts.append(section("Map parts", map_sample(), "s-map"))
    main = f'<main class="scroll" id="main"><h1 class="h1">Components</h1>{"".join(parts)}</main>'
    top = f'<div class="only-desktop">{u.topbar("map")}</div>'
    bottom = f'<div class="only-phone">{u.tabbar("map")}</div>'
    return f'<div class="col" style="min-height:100vh">{top}{main}{bottom}</div>'


# Marks the theme at the very start of <body> so a test can prove there is no flash.
BODY_START = "<script>window.__themeAtBodyStart=document.documentElement.getAttribute('data-theme');</script>"

PAGE_JS = """
(function () {
  var log = document.getElementById('event-log');
  atlas.events.forEach(function (n) { atlas.on(n, function (d) { log.textContent = n + ' ' + JSON.stringify(d); }); });
  document.getElementById('demo-toast').addEventListener('click', function () { atlas.ui.toast('Saved Corner Cafe', {action: {label: 'Undo', onClick: function () {}}}); });
  document.getElementById('demo-sheet').addEventListener('click', function () {
    atlas.ui.sheet.open({title: 'Filter places', html: '<div class="chip-row" role="group" aria-label="Types"><button type="button" class="chip" aria-pressed="true" data-autofocus>Restrooms</button><button type="button" class="chip" aria-pressed="false">Parking</button></div><button type="button" class="btn btn-primary block" data-sheet-close>Show places</button>'});
  });
})();
"""


def build(out: Path | None = None) -> Path:
    out = out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    html = u.page("Accessibility Map: components", BODY_START + build_body(), extra_js=PAGE_JS)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"{p.relative_to(ROOT)}  {p.stat().st_size // 1024} KB")
