# Morning report: browser routing (Track R), run of 2026-11-20

Branch `feature/browser-routing` (worktree `accessibility-map-routing`). Nothing pushed, merged or opened as a PR. Details per task: `docs/work_logs/routing.md`. Usage: `docs/routing_usage.md`. Screenshots: `docs/work_logs/screens/routing/` (28 PNGs, desktop 1280x800 and phone 390x844).

## What works
- **Directions panel** on the Oxford map (and Cincinnati, see below): From/To search comboboxes, My location (with an explanation first), Pick on map, swap, Wheelchair / Blind or low vision, summary (time at a stated 2.5 mph, distance, No stairs, crossings, cautions), numbered steps with icons and the word "Caution", tap a step to zoom, Previous/Next, comparison line, "Suggested from map data, not checked on site", Copy directions, Copy link, Open in Google Maps, Report a problem. Desktop side panel, phone bottom sheet. "Route here" on every card and popup.
- **Python and JavaScript agree**: 20 golden routes x 2 profiles identical (path and every string); 300 random Oxford and 135 random Cincinnati cases identical; 10 real Oxford pairs through the page identical to Python.
- **Speed/size (Oxford)**: graph 0.49 MB gzipped; panel opens in ~5 ms; first route including download ~30 ms; search under 2 ms. **Cincinnati**: 4.3 MB gzipped, long route 80 ms (worker), 308 ms worst case on a throttled main thread. Enabled.

## Commands
```bash
cd /Users/mariamzenaishvili/code/research/accessibility-map-routing
export PYTHONPATH=src ATLAS_PROCESSED_DIR=/Users/mariamzenaishvili/code/research/accessibility-map/data/processed
PY=/Users/mariamzenaishvili/code/research/accessibility-map/.venv/bin/python
$PY -m atlas.export_routing --all          # graphs -> data/map/routing/ (not committed)
$PY scripts/rerender_maps.py               # pages with the new template (already done in the last commit)
scripts/serve_routing.sh                   # then open http://localhost:8001/oxford.html  (Ctrl-C to stop)
```

## Test results (exact)
- `node --test tests/js/*.test.js`: 88 pass, 0 fail.
- `pytest tests/test_directions_ui.py`: 49 pass (incl. axe-core 4.10.2 on 7 desktop states, 3 phone heights, a card: 0 violations). In one earlier per-file run it showed "48 passed, 1 error" that I did not diagnose; two later runs were 49 passed, so treat it as a possible flake.
- `tests/test_export_routing.py` 6, `test_routing.py` 10, `test_export.py` 17, `test_report_ui.py` 14: all pass.
- Every other test file except the crawler ones passed when run one by one (assistant, discovery, extract, fusion, google_places, history, ledger, parsers, phase0, regions, report_sql, reports_export, signals).
- **Full suite NOT completed.** A single `pytest tests` run sat for over an hour. Per file: `test_crawler_c2.py` passed after 1063 s, `test_crawler_c3.py` passed (19 s), `test_crawler.py` ran 61 minutes with only 7 dots and I killed it (rc 143). I did not compare against main. These are crawler tests, which this work does not touch.
- `ruff`: no findings in my files; `ruff check src tests scripts` still shows 35 older findings in scripts (crawl_recall, eval_*, make_*).

## NOT checked
Real phone, screen reader (VoiceOver/NVDA/TalkBack), real location permission prompt, Safari/Firefox, forced-colours by eye, real Google/USGS tiles (tests use a blank tile), Cincinnati panel by eye (no screenshots; only measurements and random parity), memory use of the 12.8 MB Cincinnati graph on a phone, routes against real streets, usability with people.

## Known problems / things to look at
- Routes that look odd, probably missing OSM data (please check on the ground): Martin Dining Hall -> Yager Stadium (1.8x the straight line, 1,076 ft on a road with no sidewalk mapped); McGuffey House -> Cocks Art Museum (~400 ft no sidewalk); Oxford Lane Library -> Graeter's (blind: 474 ft no sidewalk); Center for the Performing Arts -> Peffer Park (3 steep sections).
- `routing.py` on Cincinnati: networkx raises `ValueError: Contradictory paths found` for ~2% of random pairs when stair edges have infinite cost. Could hit `export_map._route` at build time. Not changed (outside my scope). Fix idea: search with a weight function that returns None for infinite edges.
- Places far outside the walking network (e.g. Hueston Woods) give the "more than 500 feet from a mapped path" message.
- Opening the panel on desktop calls the page's `setList(true)`, which saves "list open" in localStorage.
- No in-app Help text was found in the page template, so the plan's "Directions section in Help" was not done.

## Decisions I made
Coordinates x1e7 (exact OSM precision, not 1e6); costs/lengths to 0.1 mm; Python rounding and 3.12 compensated `sum` reproduced in JS; destination = end of the place's saved route (accessible entrance) else map point, with a door note; Route here replaces the Google button on cards (Google link moved into Details and the panel) for regions with a graph; phone shows summary first; no address search; share links use `here`, never coordinates of the visitor; Cincinnati enabled after measuring; export hooked into `atlas.cli map` (4 marked lines) instead of the Makefile; regenerated `data/map/*.html` committed as a separate last commit (conflict-prone, safe to drop and regenerate).

## Hooks for the integrator
- Merge points, all marked `ROUTING`: `src/atlas/map_viewer.py` (2 imports, CSS placeholder, one JS block before the legend, three one-line `ROUTING.decorate*` calls in `card()`, `toggle()`, `popupContent()`, two `.replace` lines), `src/atlas/cli.py` (4 lines in `map`), `.gitignore`.
- Chat assistant: `window.AtlasRouting.open({toPlaceId, fromLatLng, profile})`, `AtlasRouting.isReady()`, or `window.dispatchEvent(new CustomEvent("atlas:route-to", {detail: {placeId, profile}}))`.
- After merging with the assistant branch run `python scripts/rerender_maps.py` and drop or redo the "Regenerated map pages" commit.
- The graph files (`data/map/routing/*.graph.json`, 1.4 MB and 12.8 MB raw) are git-ignored; they must be built and published next to the pages. Remove `"cincinnati"` from `ROUTING_REGIONS` in `src/atlas/routing_ui.py` if hosting 4.3 MB is a problem.
- Suggested Makefile line: `node --test tests/js/*.test.js` in `make test`. Docs for you to update: README, architecture, `data/map/README.md`, progress log.
