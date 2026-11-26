# UI and UX handout

A one-stop guide for changing the look, behaviour or screens of the Accessibility Map later. It says where things are, how a page is built, how to change something safely, how to check it, and what is still open. It points to the other docs instead of repeating them (see [README.md](README.md) for who owns which topic).

Written 2026-11-25 for the state at commit `1a5eba6` of the branch `integration/ui` (also `main`).

## 1. What the UI is

Four screens, all plain JavaScript (ES2019, no build step, no framework), each assembled into a **single HTML file** by a Python builder:

| Screen | Live file (in `data/map/`) | Built by |
|---|---|---|
| Map, Saved, place card, details, directions, city switcher | `index.html` (both cities), `cincinnati.html`, `oxford.html` | `src/atlas/map_app.py` through `map_viewer.render()` |
| Assistant chat (voice, photo, settings, My needs) | `ask.html` (loads data files next to it), `ask-standalone.html` (everything inside) | `src/atlas/assistant/page.py` |
| Rate or report form | opens inside the map page and the chat page | `src/atlas/report_form.py` plus `src/atlas/web/report/` |
| Small text page per place | `data/map/places/<city>/<id>.html` | `src/atlas/export_map.py` (not redesigned) |

Live address: `https://zenaism.github.io/accessibility-map/data/map/<file>`. GitHub Pages serves `data/map/` straight from `main`; push, then wait about a minute.

The look is style **A Harbor** (teal, soft shapes, Figtree font, Lucide icons), Light by default with an optional Dark. The basemap is USGS The National Map only, and the map stays light in Dark mode.

## 2. Where everything lives

```
src/atlas/
  ui_foundation.py         builders: head/CSS/JS, icon sprite, buttons, chips, cards, sheet, tab bar, top bar, theme switch
  web/foundation/          harbor.css (all tokens and components), foundation.js (events, sheet, toast, switches),
                           theme-boot.js (theme before first paint), icons/ (Lucide SVGs), fonts/ (Figtree)
  map_app.py               the new map page (head, search, panel, buttons, data injection)
  map_viewer.py            render() picks the new app; render(..., legacy=True) keeps the old template
  web/map/voice.js         spoken directions: AtlasVoice.words (wording), device voice, natural voice controller (D-102)
  web/map/                 map.js (state, search, cards, saved, share), map.css, nav.js (live location, directions),
                           region.js + regionui.js (city switcher, inserted into map.js at /*__REGION__*/)
  web/report/              report.js, report.css (Rate or report form), report_form.py loads them
  assistant/page.py        chat page; web/chat/{chat.js,chat.css,speech.js}; answers: assistant/composer.py + web/assistant/composer.js
  leaflet.py + web/vendor/leaflet/   Leaflet 1.9.4 and markercluster 1.5.3, vendored (no CDN)
  regions.py + config/regions.yaml   the list of cities (centre, bounding box, buffer, zoom, tier)
  ui_checks.py             measured accessibility checks used by the tests
scripts/  rerender_maps.py, build_ui_components.py, check_ui_foundation.py
tests/    test_ui_foundation, test_map_app, test_chat_app, test_report_form, test_region_switcher, test_directions_ui,
          test_vendor_leaflet, test_regions*.py; helper tests/mapdata.py; JavaScript unit tests in tests/js/
supabase/ problem_reports.sql, ratings.sql   (run once in the Supabase SQL editor; both are live)
```

Design source files (frames, style tokens, the design board, the owner's answers) are on the local branch `design/frames`, in the worktree `../accessibility-map-design/docs/design/`. They are **not** in `main`. Key ones: `CHOSEN_DESIGN.md` (the owner's decisions, 99 of 99 screens), `style/tokens/style-a-harbor.css`, `board/index.html`, and `docs/session_prompts_build.md` (the build prompts).

## 3. How a page is made

1. Python builders return HTML strings. The page head is `ui.head_snippet()` (sets `data-theme` before paint, defines `window.atlasTheme`), then `ui.css()`, `leaflet.head()` and the screen's own CSS.
2. Every foundation rule sits under a parent class `ax`; a page without `ax` is not restyled.
3. The JS files are concatenated inline. The map page also injects the data (`window.__MAPDATA`, `window.__MAPCFG`, `window.__REGIONS`) so it works from a file or a server with no extra requests.
4. Rebuild after any change to the page code (data is kept as it is):

```bash
python scripts/rerender_maps.py          # index, cincinnati, oxford (reads the data back out of the existing pages)
python -m atlas.assistant.page           # ask.html and ask-standalone.html
```

`make map` rebuilds all data too and can change hundreds of files: use it only when the data changed. Then commit, push, wait a minute.

Network: the pages contact only their own host, the USGS basemap and (only when someone sends or deletes a report) Supabase. A test fails if anything else is requested.

## 4. Rules a change must keep

- **Tokens only.** Use `--bg`, `--surface`, `--text`, `--primary`, `--control`, `--focus` and the spacing and radius tokens from `harbor.css`. No new colours, fonts or icons in a screen file. Add a missing component or icon to the foundation instead, and note it in [ui_components.md](ui_components.md).
- **44 px targets**, a 3 px focus ring, text 4.5:1, control borders and icons 3:1, in Light and Dark. A name for every control. Nothing conveyed by colour alone (ratings are symbol plus word).
- **Motion** honours `prefers-reduced-motion`. Phone and desktop split at 900 px (`.only-phone`, `.only-desktop`).
- **Short words, list first.** The audience is wheelchair and low-vision users outdoors on phones. The map is a companion: everything on it is also in the list.
- **Language:** screen text is plain, short, US English; no jargon.
- **Free tools only, no tracking, nothing sent in Guided mode.** No paid services.
- **Do not hand-write colours into JS**, except the map pins, which use fixed colours with an outline in both themes.
- Hard-won ones: do not put `<header>` twice on a page (one banner landmark); keep `ui.button(type="submit")` for form buttons; a hint that appears on focus must float (`position:absolute`) so it cannot shift the layout and swallow the tap; guard code that runs before markers exist (`markersReady`).

More: the checklist in [ux_brief.md](ux_brief.md) section 6, the style guide in section 7.

## 5. The foundation in one page

Full list with classes: [ui_components.md](ui_components.md). The parts people change most:

- **Theme.** `atlasTheme.get()` and `atlasTheme.set("light"|"dark")`; stored in `localStorage` key `atlas.theme`; fires `atlas:theme-changed`. The sun and moon switch is `ui.theme_toggle()` (a `role="switch"` named "Dark theme", sun left, moon right); `foundation.js` keeps every theme control in step. The map's phone bar and desktop top bar have it instead of Settings. The chat keeps Settings and adds the switch (header on phones, top bar on desktop).
- **Events on `document`** (`atlas.on(name, fn)`, `atlas.emit(name, detail)`): `atlas:open-report {placeId, region}`, `atlas:open-saved`, `atlas:open-ask {placeId?}`, `atlas:region-changed {region}`, `atlas:theme-changed {theme}`. A click on any element with `data-atlas-emit="…"` fires one. This is how the screens talk without importing each other.
- **Sheet and toast:** `atlas.ui.sheet.open({title, html|node, onClose})` (focus trap, everything else `inert`, Escape closes); `atlas.ui.toast(text, {action})`.
- **Navigation:** phone tab bar Map, Saved, Ask, Report (60 px); desktop top bar brand, Map, Saved, theme switch, Settings (chat only), Report a problem, Ask.
- **Report form on any page:** a page without the map's data calls `AtlasReport.setPlaces([{id, name, region, rating, layer, pt}])`; `data-rp-inert` on an element tells the form what to freeze while it is open.

## 6. Behaviour that is easy to break

| Area | Facts to keep |
|---|---|
| City as a variable | `config/regions.yaml` is the only list. Rule on the device: a position inside a region's bounding box grown by `buffer_km` is covered; the smallest distance to the centre divided by the buffer wins. Choice order: `?region=` in the link, then the saved choice (`atlas-region`), then the closest, then "Choose a city". `tier: full` cities have all layers, `limited` have places and what the city publishes. Add a city: add its block to `regions.yaml` and build its data; the switcher, notice and assistant text follow. |
| Saved places | Stored on the device only: `atlas-favs-v2` (`{id, region}`; legacy `atlas-favs`), a snapshot `atlas-fav-snap` for changed or removed places, restore link in the URL fragment `#saved=…`. Save is one visible word, no `aria-pressed`, with undo on the Saved page. |
| Links | `?region=<city>#place=<id>` opens a place; Copy link on the place card is one tap. |
| Reports | `atlas-device` (random id), `atlas-my-reports`, `atlas-report-draft-v2-…`, `atlas-rated-…`. The form shows only if the database answers `report_ping()`. Rating is for Cincinnati and Oxford only. SQL contract tests: `tests/test_report_sql.py`. |
| Chat answers | One short answer: headline of at most 25 words, one confidence line, the nearest confirmed place first, one card, "More", three follow-up chips (16 px). The rules exist twice, in Python (`composer.py`) and JavaScript (`composer.js`); change both and run the golden tests (`tests/js/assistant_golden.json`) so they agree. |
| Voice | Browser speech recognition; if the browser stops at a pause the app restarts after 350 ms and keeps what was said. Voice and photo need HTTPS or `localhost`. |
| Chat prefs | `openway.prefs` (answer mode, text size, plain language), `openway.needs` (My needs), `openway.gaps` (questions not answered, kept on the device). |
| Directions | Walking route graph in `data/map/routing/oxford.graph.json`; only Oxford has routing so far. Live position uses the bottom card. Spoken directions: `web/map/voice.js` (wording, device voice, natural voice) and `data/map/tts/` (Kokoro files); Voice is off by default (D-102). |

## 7. How to make a change safely

1. Read the owner of the part in the "Who owns which file" table of [ui_components.md](ui_components.md).
2. Write down the change and why. Add a numbered entry **at the top of** [decisions.md](decisions.md) (decision, why, alternatives, costs, basis); the next free number is **D-102**. Add a progress-log row to [progress_log.md](progress_log.md). If the design changes, update the diagrams in [architecture.md](architecture.md) (sections 13 to 19 cover the UI).
3. Work on a branch from `integration/ui` (or `main`; they are the same now). Change the screen's own file; touch the foundation only for a shared component.
4. Test while you work:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_map_app.py -q          # or the file of the screen you changed
python scripts/check_ui_foundation.py --shots build/shots                    # measured accessibility and screenshots
.venv/bin/ruff check src tests
```

   Browser tests use Playwright with Chromium and a fake Supabase and fake speech, so they run offline. The full run takes about 13 minutes: `make test`. **Expected result today: 2 failures** (`test_area_conditions_hills_and_reports`, `test_all_bank_questions_give_verified_answers`), which need `data/processed`.
5. Rebuild the pages (section 3), look at them at 375 px and 1280 px in Light and Dark, commit, push, reload the live page after a minute.
6. Before committing: run `git status`, never commit `data/map/ask.html` as a side effect of a test run (several older tests rewrite it; `git checkout data/map/ask.html` first, then rebuild it deliberately), and let the gitleaks hook run (never `--no-verify`).

Commit as Mariam Zenaishvili `<zenaism@miamioh.edu>`, with no AI co-author line, by explicit file paths.

## 8. Recipes

- **Change a colour or size:** edit the token in `harbor.css` (Light block and Dark block); run the contrast check (`check_ui_foundation.py`).
- **Add an icon:** drop a Lucide SVG into `web/foundation/icons/`; it joins the sprite; use `ui.icon("name")`.
- **Add a button to the app bar:** edit `map_app.py` (phone bar and `ui.topbar` for desktop) or `assistant/page.py`; give it an accessible name; make sure the 44 px target and the phone width (320 px) still fit.
- **Change a screen's text or layout:** the map is in `web/map/map.js` (functions such as `viewCard`, `viewDetails`, `saveBtn`) and `map.css`; the chat in `web/chat/chat.js` and `chat.css`; the form in `web/report/report.js` and `report.css`.
- **Add a setting:** chat settings are built in `buildSettings()` in `chat.js`. The map has no settings sheet any more (D-101).
- **Add a city to the switcher:** `config/regions.yaml` (section 6).
- **Update Leaflet:** replace the four files and the versions in `web/vendor/leaflet/README.md`; the vendor test checks the file hash, update it.
- **Change the answer wording or rules:** section 6, chat answers.

## 9. What is open (UI and UX)

- **Real devices not tested.** Everything was tested in headless Chromium only. Still to try on a real iPhone and Android phone: compass and heading, live location, voice, the keyboard on the compose field, photo and camera, and a screen reader (VoiceOver, TalkBack). The headless run cannot find problems with these.
- **Sending a report from a phone** has not been done end to end (the database functions were checked with harmless probe calls).
- **Spoken route directions** are built (D-102) but only tested in headless Chromium: try the device voice and the natural voice (Kokoro, 92 MB) on a real iPhone and Android phone, with a screen reader on. **Rating regions** beyond Cincinnati and Oxford are deferred.
- **City names in the data pipeline** (`export_map.py`, `fusion.py`) are still fixed to Cincinnati and Oxford (D-92); the UI reads the region list, the pipeline does not yet.
- **Small places the design shows but the build skips:** see "Differences from the frames" and the "Gaps" sections at the end of [ui_components.md](ui_components.md).
- **Decision log:** D-40 to D-42 were renumbered (saved places D-93 to D-95, map D-96 to D-98); the README entries keep D-40 and D-41, the UI base entry keeps D-42.

## 10. Where to read more

| Topic | Document |
|---|---|
| Component and class list, event contracts, who owns which file, gaps found while building | [ui_components.md](ui_components.md) |
| Users, ranked tasks, audit, research, requirements checklist, style guide | [ux_brief.md](ux_brief.md) |
| Flows, branch layout, foundation, map app, report, chat, city as a variable (sections 13 to 19) | [architecture.md](architecture.md) |
| Why each choice was made (D-49 to D-101 are the UI) | [decisions.md](decisions.md) |
| What was done when | [progress_log.md](progress_log.md) |
| Reports: form, SQL, export for the team | [problem_reports.md](problem_reports.md) |
| Routing in the browser | [routing_in_browser_plan.md](routing_in_browser_plan.md), [routing_usage.md](routing_usage.md) |
| Whole system and data | [system_overview.md](system_overview.md) |
