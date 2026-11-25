# Directions on the map: build, serve, use, limits

The Oxford and Cincinnati maps have a **Directions** panel: pick a start and a destination and get a step-free
walking route with directions in words, computed **in the visitor's browser**. Python decides the rules (which
paths cost more); JavaScript only searches and words the result. Nothing is sent to any server.

## Build

```bash
# 1. the walking graph for every region that has the panel (also done by `make map` / `python -m atlas.cli map`)
python -m atlas.export_routing --all            # or: --region oxford
#    -> data/map/routing/<region>.graph.json   (generated, git-ignored; prints raw and gzipped size)

# 2. the map pages (new template with the panel). If only the page template changed:
python scripts/rerender_maps.py                 # keeps the data already in the pages
#    or the full build: make map

# 3. golden test routes (only when the routing rules or wording in src/atlas/routing.py change)
python scripts/make_golden_routes.py --region oxford
```

Which regions get the panel is `ROUTING_REGIONS` in `src/atlas/routing_ui.py`. A region without a graph keeps
the old Google Maps "Directions" link and shows no Directions button.

## Serve and open

Browsers cannot fetch the graph from `file://`, so serve the folder over HTTP:

```bash
scripts/serve_routing.sh            # http://localhost:8001/oxford.html   (localhost only; Ctrl-C stops it)
scripts/serve_routing.sh 8002       # another port
```

On GitHub Pages the graph files in `data/map/routing/` must be published next to the pages
(they are not committed; publish them with the release, as with other generated data).

## Use

* **Directions** (top bar) opens the panel. **Route here** on any place card or map pop-up opens it with the
  destination filled in and the start set to *My location* (the browser is asked only after a short explanation).
* Start and destination are places from the map (type to search), *My location*, or *Pick on map*.
* *Wheelchair* avoids stairs, steep sections, rough surfaces and raised curbs. *Blind or low vision* also prefers
  signalled (ideally audible) crossings and says what each crossing has.
* The result shows time (at a stated 2.5 mph, an estimate), distance, "No stairs", crossings in words, cautions,
  numbered steps (tap one to zoom the map to it), Previous / Next, Copy directions, Copy link, Open in Google
  Maps and Report a problem. Every route says "Suggested from map data, not checked on site."
* Share links look like `oxford.html#route=<from>,<to>&profile=wheelchair`; each end is a place's `link_id`,
  `@lat;lon`, or `here` (the opener's own location, never stored in the link).
* For other code (the chat assistant): `window.AtlasRouting.open({toPlaceId, fromLatLng, profile})`,
  `AtlasRouting.isReady()`, or `window.dispatchEvent(new CustomEvent("atlas:route-to", {detail: {placeId, profile}}))`.

## Files

| File | What |
|---|---|
| `src/atlas/export_routing.py` | writes the graph (costs from `routing.penalty()` / `blind_penalty()`) |
| `src/atlas/web/routing.js` | graph loading, snapping (150 m limit), A* search |
| `src/atlas/web/directions.js` | directions in words, ported line by line from `routing.py` |
| `src/atlas/web/panel.js`, `panel.css` | the interface |
| `src/atlas/routing_ui.py` | inlines the above into the map page (`__ROUTING_JS__`, `__ROUTING_CSS__`) |
| `tests/golden_routes_oxford.json` | 20 Python routes the JavaScript must reproduce exactly |
| `tests/js/*.test.js`, `tests/test_directions_ui.py`, `tests/test_export_routing.py` | the tests |

## Tests

```bash
python -m pytest -q tests/test_export_routing.py tests/test_routing.py
node --test tests/js/*.test.js
npm install axe-core@4.10.2 --no-save --prefix ./.axe        # once, for the accessibility checks (skipped if missing)
python -m pytest -q tests/test_directions_ui.py              # Chromium via Playwright; Leaflet is inside the page, no download
```

## Limits

* Routes follow OpenStreetMap paths and USGS elevation. Missing sidewalks, curb ramps and recent changes are
  not known. Nothing is checked on site; the panel says so on every route.
* Points more than 150 m (500 feet) from a mapped path are refused with a message.
* Time is an estimate at 2.5 mph, a guess until a source is found.
* No address search (it would send what people type to an outside service), no live navigation, no bus
  routes, no indoor routes, no stops in between.
* A place's route ends at its accessible entrance only when the saved bus-stop route knows one; otherwise it
  ends at the place's map point and the steps say so.
* Phones and screen readers have not been tried by a person yet (see `docs/work_logs/RUN-routing.md`).
