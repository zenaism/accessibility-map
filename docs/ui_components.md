# UI components (foundation B0)

The shared look and behaviour of the Accessibility Map, style A Harbor. One Python module, `src/atlas/ui_foundation.py`, returns the CSS, the icon sprite and the JavaScript; the files it reads are in `src/atlas/web/foundation/`. Build sessions B1 to B4 use these and do not edit each other's files. Why and what was decided: D-68 to D-71 in [`decisions.md`](decisions.md). Diagram: [`architecture.md`](architecture.md) section 15.

## Use it in a page generator

```python
from atlas import ui_foundation as ui
html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{ui.head_snippet()}              <!-- sets data-theme before first paint, defines window.atlasTheme -->
<style>{ui.css()}</style></head>
<body class="ax">{ui.body_snippet()}   <!-- the icon sprite -->
  ...page...
<script>{ui.js()}</script></body></html>"""
```

Rules: every rule in the foundation CSS needs a parent with class `ax`, so a page that does not add `ax` is not restyled (existing screens stay as they are until their own build). Tokens (`--bg`, `--surface`, `--text`, `--primary`, `--focus`, `--control` ...) exist only inside `.ax`; write new CSS with the tokens, never a hex colour. `ui.css()` inlines Figtree (about 45 KB); `ui.css("fonts/")` links the `.woff2` files instead (copy them from `src/atlas/web/foundation/fonts/`). No request leaves the page.

## Theme

Light is the default and the app does not follow the device setting. The choice is stored on the device (`localStorage` key `atlas.theme`, in try/catch) and applied as `<html data-theme="light|dark">` by a script in `<head>`, so there is no flash.

```js
atlasTheme.get();        // "light" | "dark"
atlasTheme.set("dark");  // stores, applies, fires atlas:theme-changed; returns the theme now in use
```

Anything other than `"dark"` means Light. If storage is blocked the choice lasts until the page closes. `ui.appearance_group()` is the Settings row (Light / Dark, native radios `name="atlas-theme"`); foundation.js keeps it in step with `atlasTheme`. The USGS basemap stays light in dark mode: `--map-*`, `--pin-*`, `--user-dot` and `--route` are the same in both themes, pins have a dark outline and a white halo.

## Events

All on `document`, payload in `event.detail`. `atlas.on(name, fn(detail, event))` returns an `off()` function. `atlas.emit(name, detail)` returns how many real listeners took it (0 before the owning build lands) and never throws. A no-op listener is built in for every name.

| Event | Payload | Fired by | Listener owner |
|---|---|---|---|
| `atlas:open-report` | `{placeId, region}` (both optional) | Report tab, desktop Report button, place-card Report button | B2 (report) |
| `atlas:open-saved` | `{}` | Saved tab and Saved link | B1 (map and Saved) |
| `atlas:open-ask` | `{placeId?}` | Ask tab and button, "Ask about this place" | B3 (chat) |
| `atlas:region-changed` | `{region}` | the city switcher | B4 (city) emits and listens; others may listen |
| `atlas:theme-changed` | `{theme}` | `atlasTheme.set()` | anyone |

Markup shortcut: an element with `data-atlas-emit="atlas:open-report" data-place-id="..." data-region="..."` fires the event on click (`ui.button(..., emit=..., place_id=..., region=...)`). If the element is a link and a listener took the event, the default navigation is cancelled; if nobody listens the plain `href` is followed, so a page works before the other builds exist. Give such links a real `href`.

## Components

Python builders return HTML strings; classes can be used by hand.

| Component | Builder | Classes and notes |
|---|---|---|
| Button | `button(label, kind, icon, icon_only=, block=, href=, emit=)` | `.btn` + `.btn-primary` / `-secondary` / `-ghost` / `-danger`; `.btn-icon` (44 px square, `.round`); `.block`; disabled and `aria-busy` styles. Icon-only buttons get `aria-label`. One primary button per screen. |
| Chip | `chip(label, pressed)`, `chip_row` | `.chip[aria-pressed]` with a check mark when on; `.chip-row` scrolls sideways. |
| Search field | `search_field(placeholder, value, id=, label=)` | `.search` with `role=search` (give each one a different label). |
| Text field | `text_field(label, id=, hint=, error=, multiline=)` | `.field`, `.input`, `.textarea`, `.hint`, `.err`; error is linked by `aria-describedby`, `aria-invalid`. |
| Switch | `toggle(label, checked, id=)` | `.toggle[role=switch][aria-checked]`; fires `atlas:switch` on the element. |
| Radio group | `radio_group(label, [(value, text)], value, id=)` | `.choice[role=radio]` in `role=radiogroup`; arrow keys; fires `atlas:choice {value}`. |
| Appearance | `appearance_group(current)` | `.seg` native radios `name=atlas-theme`. |
| Stars 1 to 5 | `star_rating(name, value)` | `.stars` `.star`, native radios, for the report form (B2). |
| Rating badge | `rating_badge(rating, large=, reported=)` | `.badge.yes/.partial/.no/.unknown`; always symbol + word: Accessible, Partly accessible, Not accessible, Not known. **The ring on Partly accessible is the badge's own text colour (`border-color: currentColor`, 2 px): one ring colour, no second hex.** |
| Place card | `place_card(name, rating, facts, source, place_id=, region=)` | variant B (rating first): `.place.card`, `.ratetile`, `.stat3`, `.conf`; Route here, Save, More details, Report a problem (fires `atlas:open-report`). |
| Bottom sheet, docked | `sheet(title, body, id=)` | `.sheet` + `.grab`. |
| Bottom sheet, modal | JS `atlas.ui.sheet.open({title, html \| node, onClose})` | `role=dialog aria-modal`, focus trap, Escape and scrim close, everything else `inert`, focus returns to the opener. Put `data-autofocus` on the control to focus first; `data-sheet-close` closes. |
| Banner | `banner(text, "warn"\|"info", action=)` | `.banner` `role=status`. |
| Toast | JS `atlas.ui.toast(text, {action: {label, onClick}})`; static `toast()` | live region `polite`, 6 s (10 s with an action). |
| Empty / error state | `state(title, text, icon, error=)` | `.state`, `.state.error` (`role=alert`). |
| Tab bar (phone) | `tabbar(active, hrefs)` | `.tabbar.four` Map, Saved, Ask, Report (flag icon, name "Report a problem"), 60 px tall, `aria-current="page"` on the active one; `atlas.ui.setTab(name)` moves it. |
| Top bar (desktop) | `topbar(active, hrefs)` | `.appbar.top` brand, Map, Saved, Settings, Report a problem (secondary), Ask (the one filled button). Use `.only-phone` / `.only-desktop` (breakpoint 900 px) to show one of the two. |
| Map parts | classes `.pin.yes/.partial/.no/.unknown`, `.you` (`.ring`, `.dot`), `.routecase` + `.routeline` | fixed colours in both themes. |
| Icons | `icon(name)`; JS `atlas.ui.icon(name)` | `<svg class="ic"><use href="#lucide-NAME"/></svg>`, `currentColor`; names: `ui.icon_names()`. `more` is the circled "i" drawn in the frames; `dots` is the three-dot overflow icon; `share` is the link icon used for "Copy link"; `copy`, `sun`, `moon` are Lucide additions (not in the frames). |

Targets are 44 px or more; focus is a 3 px ring in `--focus`; motion honours `prefers-reduced-motion`.

## Check it

```bash
python scripts/build_ui_components.py                     # build/ui_components/components.html (not shipped, git-ignored)
python scripts/check_ui_foundation.py --shots build/shots # measured: contrast, targets, names, focus, requests, scroll, axe
pytest tests/test_ui_foundation.py
```

The checks run the page at 375 and 1280 px in Light and Dark and fail on: text under 4.5:1 (3:1 for large text), control borders, icons or focus rings under 3:1, a target under 44 px, an interactive element without an accessible name, a visible-focus gap, any request that leaves the local server, horizontal scroll, and (when `.axe` is installed, see `tests/test_assistant_ui.py`) any axe violation. Disabled controls are exempt from contrast (WCAG 1.4.3).

## Who owns which file

| File | Owner | Others |
|---|---|---|
| `src/atlas/ui_foundation.py`, `src/atlas/web/foundation/*` (CSS, JS, icons, fonts), `src/atlas/ui_checks.py`, `src/atlas/ui_components_page.py`, `tests/test_ui_foundation.py`, this doc | B0 | read only; ask for a new component or icon by adding it here in a follow-up B0 change, not by editing in a screen build |
| New map app: `src/atlas/map_app.py`, `src/atlas/web/map/{map.css,map.js,nav.js}`, `tests/test_map_app.py`; `map_viewer.render()` dispatch (`legacy=True` keeps the old page) | B1 | call the builders; listens for `atlas:open-saved`, fires `atlas:open-report` and `atlas:open-ask` |
| Report form (`report_ui.py`, `supabase/ratings.sql` and the report JS) | B2 | listens for `atlas:open-report` |
| Chat page (`assistant/page.py`, `web/assistant/*`) | B3 | listens for `atlas:open-ask`; Settings Appearance row uses `appearance_group()` |
| City switcher and first-open sheet (new files) | B4 | emits and listens for `atlas:region-changed` |

Screen-specific CSS goes in the screen's own file, scoped under `.ax`, built from tokens. Do not add colours, icons or events to the foundation from a screen build.

## Differences from the frames (found while building)

1. The frames set the app-bar buttons to a transparent border and background, which hid the secondary border on desktop "Report a problem" (measured 1.0:1) and would blank the filled Ask. The foundation restores them (`.ax .appbar .btn-secondary`, `.btn-primary`).
2. The inverse toast's Undo button had a 2.5:1 (light) and 1.8:1 (dark) focus ring. Its ring now uses the toast text colour.
3. The Partly accessible ring is 2 px (the frames' 1.5 px renders as 1 px at normal pixel density).
4. "copy-link": the frames use the link icon (`share`); a `copy` icon is also in the sprite.

## Gaps B1 found in the foundation (B0 to decide; B1 worked around them in `map.css`)

- Not in `harbor.css` although the chosen frames use them: `.tile-grid.three` and `.tile.sm` (type tiles), `.opt` (a bordered group), `h3.sec`, a `[hidden]` rule that beats `.btn { display: inline-flex }`, hiding the native clear button in `input[type=search]`, and a 44 px minimum for inline links inside the panel (`.dfact a`, `ul.plain a`). B1 defines these under `.ax` in `map.css`; if B2 and B3 need them too, move them into `harbor.css`.
- The desktop frames have no Back control; B1 adds one in the panel (D-76).
- `atlas.ui.toast` has no way to place itself above a docked panel; on phone it overlaps the bottom of the sheet for 6 to 10 seconds.
