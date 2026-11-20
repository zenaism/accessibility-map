# Work log: browser routing (Track R)

Branch `feature/browser-routing`, worktree `accessibility-map-routing`. Started 2026-11-20 (overnight run).

Environment note: the shell did not have PYTHONPATH/ATLAS_* exported. I used
`PYTHONPATH=src ATLAS_PROCESSED_DIR=<main checkout>/data/processed` (read-only use of the main checkout's data) with the main venv's python.

## R1 export graph + golden routes
Did: `src/atlas/export_routing.py` (`python -m atlas.export_routing --region oxford`), `scripts/make_golden_routes.py`, `tests/golden_routes_oxford.json` (20 pairs, 93 KB), `tests/test_export_routing.py` (6 tests pass, with tests/test_routing.py).
Measured: Oxford 21,637 nodes, 25,425 edges (11 parallel edges dropped by routing.network), raw 1.42 MB, gzipped 0.48 MB (target 2 MB). Export takes ~2 s.
Golden file: avoids stairs x3, steep x2, many crossings x3, blind-differs x2, road without sidewalk, short, long, shortest-is-easiest, no step-free route x2 (real: both ends snap, stairs or gap in the way), same point, too-far x2. No raised-kerb pair was found by the seeded search (not covered by a golden pair).
Not checked: Cincinnati (R10).
Decisions I made:
- Coordinates are degrees x **1e7** (not 1e6 as in the plan): OSM stores 7 decimals, so this is exact and bearings/turn wording cannot differ from Python because of rounding.
- `len` and costs are rounded to 0.1 mm (4 decimals), so JS and Python sums round to the same feet.
- Edge columns are columnar parallel arrays (gzip-friendly). Flags are a bit field; crossing kind is an index into the raw `crossing=*` strings so JS can apply Python's exact (case-sensitive / lower-cased) comparisons.
- Golden file stores the node-index path per profile and drops `line` and `note` (derivable, keeps the file small).

## R2 JavaScript search, R3 directions in words
Did: `src/atlas/web/routing.js` (UMD: loadGraph, grid snap with the 150 m limit, A* with a binary heap for both profiles, shortest-with-stairs, edgeBetween), `src/atlas/web/directions.js` (line-for-line port + `route()` that returns the Python result shape plus step kinds/warnings/leg index ranges for the UI), `tests/js/routing.test.js`, `tests/js/directions.test.js`, `tests/js/helpers.js`.
Measured: `node --test tests/js/*.test.js`: 87 pass, 0 fail. All 20 golden pairs x 2 profiles reproduce the Python **node path exactly** (no equal-cost tie differences) and **every string exactly** (directions, length_feet, compared_with_shortest, crossings_text, crossings counts, shortest, snap_feet).
Extra check (not in the committed suite, needs Python): `scripts/check_routing_parity.py` + `.js` on 300 random cases (150 node pairs jittered up to ~30 m, both profiles): 288 identical results, 12 both-null, 0 mismatches.
Not checked: Python/JS agreement on different CPUs/Node versions for atan2/cos last-digit differences (none seen).
Decisions I made:
- Python-number behaviour reproduced on purpose: banker's `round()`, `round(x,1)`, `f"{x:.1f}"` ties-to-even, and Python 3.12's compensated `sum()`; `radians`/`degrees` written as x*(pi/180) like CPython.
- A* heuristic uses the graph's lowest cost/length ratio (0.9 for blind because tactile crossings multiply by 0.9) with 2% slack, and allows re-opening, so it is optimal.
- `directions.js` adds `stepList` (kind, warnings, feet, fromIdx/toIdx) beside the golden strings: the UI needs icon kind, a "Caution" flag and the part of the line to zoom to. The step text is exactly the Python string.

## R5 Directions UI, R6 browser tests
Did: `src/atlas/web/panel.js` (+ `panel.css`), `src/atlas/routing_ui.py` (reads the web files; inlines them like REPORT_JS), minimal marked changes in `src/atlas/map_viewer.py` (CSS placeholder, one JS placeholder block, three one-line `ROUTING.decorate*` calls in card(), toggle() and popupContent()), `scripts/serve_routing.sh`, `scripts/routing_screenshots.py`, 28 screenshots in `docs/work_logs/screens/routing/`, `tests/test_directions_ui.py`.
UI: From/To comboboxes (ARIA 1.2: role=combobox, listbox, aria-activedescendant), My location (with an explanation box before the browser prompt, skipped when permission is already granted), Pick on map, swap, Wheelchair / Blind or low vision (remembered locally), summary (time at a stated 2.5 mph, distance, No stairs, crossings sentence, cautions), numbered steps with icons and the word "Caution", tap a step to zoom, Previous/Next, comparison line, "Suggested from map data, not checked on site", Copy directions, Copy link (#route=from,to&profile=), Open in Google Maps, Report a problem (the map's own form, GitHub fallback link), Web Worker from a Blob (inline fallback), graph loaded on first open (prefetch on hover/focus of the button), white casing + dark blue line, big Start/End pins, signs on the route for crossings and cautions, `window.AtlasRouting` and the `atlas:route-to` event, desktop side panel / phone bottom sheet (summary / steps / full list).
States covered by tests and screenshots: empty, loading, location asked, location denied, searching (transient), route found, too far from a path, no step-free route, same place, load error (with Retry), unavailable region, two cities, picking on the map, and the door note.
Measured: `python -m pytest tests/test_directions_ui.py`: 47 passed in ~16 s, including axe-core 4.10.2 (wcag2a/2aa/21a/21aa + best-practice, which includes colour contrast) on 7 desktop states, 3 phone sheet heights and a place card: 0 violations. I checked axe really flags problems with a deliberately bad snippet.
Not checked: a real phone, a screen reader (VoiceOver/NVDA/TalkBack), a real location permission prompt, Safari/Firefox, forced-colours appearance by eye (only that casing and line differ in colour), Google basemap tiles (tests replace tiles with a blank image).
Decisions I made:
- Destination = the end of the place's saved bus-stop route (an accessible entrance, when one is mapped) else the place's map point; when the saved route says no door is mapped the steps get that note. (The geojson has no entrance coordinates; adding them would change the data pipeline.)
- Route here replaces the Google "Directions" button on cards and popups for regions with a graph; the Google Maps walking link moves into Details ("Directions in Google Maps") and into the panel. Regions without a graph keep the old link and get no Directions button.
- On a phone a found route shows the summary first (map visible); "Steps" opens the list, "Full list" fills the screen.
- Typing in a field drops its old choice; editing one end while the other is set re-routes at once.
- Free address search is not included (privacy, as the plan says).
- Escape closes the suggestions first, then the panel, and returns focus to the button that opened it.
- Share links never contain "My location": they say `here`, so whoever opens the link is asked for their own location.
- Fixed while testing: the suggestion list closed itself 120 ms after an earlier blur when the user clicked back into the field quickly.
