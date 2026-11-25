# Publishing the map with Directions and the chat (checklist)

Branch: `deploy/routing-pages` (from `integration/routing-assistant`, which merges `feature/browser-routing` and `feature/assistant`). Local only: nothing is pushed, nothing merged into `main`.

## What is on the branch
- Directions panel + "Route here" on the Oxford map, the chat assistant (map panel and `ask.html`), chat "Route here" opening the Directions panel.
- **Routing is on for Oxford only** (`ROUTING_REGIONS` in `src/atlas/routing_ui.py`). Cincinnati keeps its Google Maps links. It is measured and works (graph 4.3 MB gzipped); to turn it on see "Cincinnati" below.
- The Oxford walking graph is **committed** (`data/map/routing/oxford.graph.json`, 1.4 MB, about 0.5 MB on the wire). Pages only serves committed files and there is no CI build, so it has to be in git. (On the feature branches graphs are git-ignored; the deploy branch force-adds this one file.)
- Map pages (`oxford.html`, `cincinnati.html`, `index.html`) re-rendered with the new template; `ask.html` and `ask-standalone.html` rebuilt by the assistant branch.

## Checked locally (not on GitHub)
- Served the repo root and opened `/data/map/oxford.html#route=...`, the same path layout as `https://zenaism.github.io/accessibility-map/data/map/`: the graph loaded (HTTP 200), a route was found, no JavaScript errors. `cincinnati.html` still shows the 20 Google links and no Directions button.
- `tests/test_directions_ui.py`, `tests/test_export_routing.py`: 55 pass. Earlier on the integration branch: assistant UI + routing UI + report UI together 92 pass; `node --test tests/js/*.test.js` 178 pass.
- NOT run: the slow crawler tests and the rest of the suite on this branch.

## Before you publish (you decide each step)
1. **Review the diff.** `git diff main...deploy/routing-pages --stat`. The map pages are large generated files, so expect big diffs there.
2. **Run the tests you care about** (see above) and try http://localhost:8003-style local serving once more: `scripts/serve_routing.sh`, open `oxford.html`, click Directions, try Route here from a chat answer.
3. **Merge into `main`** (or push the branch and open a PR so someone can look first). If other work landed on `main` since, re-run `python scripts/rerender_maps.py` after merging: conflicts in `data/map/*.html` are expected and are resolved by regenerating them.
4. **Push.** Pages rebuilds in about a minute (the skill notes say Pages serves from the repo root: `.../data/map/oxford.html`).
5. **Check the live site** (only possible after publishing): open `.../data/map/oxford.html`, open the browser's network tab, click Directions, confirm `routing/oxford.graph.json` is fetched with status 200 (served gzipped), a route appears, and Route here from the chat works. If the panel says "We could not load the walking map", the graph file did not get published or the path is wrong.
6. **Share the link** and say what it is: routes are suggestions from OpenStreetMap and elevation data, not checked on site; Guided chat mode only (no local model, photos or voice-to-model on the hosted site).

## Known limits to tell testers
- Needs internet for the USGS map tiles (the map library is inside the page); works in modern phone and desktop browsers (tested in headless Chromium only: not tried on a real phone, Safari, Firefox or with a screen reader).
- The chat's Local model mode, photo and model voice need your own computer and do not work on the hosted page.
- Oxford only for Directions.

## Cincinnati (optional, later)
Add `"cincinnati"` to `ROUTING_REGIONS`, run `python -m atlas.export_routing --all`, `git add -f data/map/routing/cincinnati.graph.json` (12.8 MB raw, 4.3 MB gzipped; GitHub warns above 50 MB, so it is fine but heavy), run `python scripts/rerender_maps.py`, update the test expectations if needed, and test.

## Open issues carried over
See `docs/work_logs/RUN-routing.md` (odd routes to check on the ground, the `routing.py` networkx error on Cincinnati, untested devices).
