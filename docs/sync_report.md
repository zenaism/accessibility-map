# Sync report: localhost vs GitHub Pages

Refreshed 2026-11-26 (night), after the restore commits `9d0d21a` (crawl specs) and `b25fe70` (data cards) were pushed on top of the city-page and GitHub-link commit `4ff095b`. Not committed. Earlier versions of this report described a diverged state and a pending question list; both are closed.

## Verdict: in sync

Local `main`, `origin/main` and the live Pages site are all at `b25fe70` (0 ahead, 0 behind, no tracked changes). The page and data files under `data/map/` have not changed since `4ff095b`: the two later commits touched only `config/crawl/` and `data/cards/`, so the hash comparison below (done at `4ff095b`, build "built") still holds. I did not re-download the live files after the two data-only pushes. All eleven files I downloaded from Pages have the same SHA-1 as the working copy, and a fresh render from the current generator (`atlas.map_viewer.render`, held in memory, nothing written to the repo) equals the committed `index.html`, `cincinnati.html` and `oxford.html`. So no generated page is out of date with the generator, and localhost runs the same code and data as Pages. The only differences left come from the browser and the CDN, not from the repo.

## How we got here

1. First report: local `main` was 71 commits ahead and 131 behind `origin/main`; localhost showed the old design, Pages the redesign.
2. Uncommitted "size 80" work saved first (`bf0eb23`), rebased onto `origin/main` as `06e37d2`, tested, pushed, deployed. The backup branch `backup/size-80-wip` and its worktree were deleted afterwards (the work is in `main`; `bf0eb23` was never on a remote).
3. Old local `main` and its uncommitted edits saved on `backup/old-local-main-2026-11-26` (`0dfdc2c`); local `main` reset to `origin/main`.
4. `4ff095b` (this report's base): city pages open their own city even when another is saved; the GitHub report fallback was removed from the pages (report banner, route alert, assistant, Report tab); the tests were updated, one test added. Pushed and deployed.
5. `9d0d21a`: restored `config/crawl/places_oxford_food.json` and `places_oxford_venues.json` (the only crawler files missing; the crawler code, extractor, tests and docs were already on `main`, identical to the backup). Pushed.
6. `b25fe70`: regenerated the dataset cards with `make cards` (the backup's copies were a stale 2026-11-19 snapshot, differing only in `age_days`). Pushed.
7. Design board and prototypes (`docs/design/`, `docs/prototypes/`, 481 files) copied back into the working folder from the backup branch. They are git-ignored on purpose (`.gitignore` lines 51-52, "never commit these"), so they are not in git.
8. `docs/session_prompts.md`, `docs/session_prompts_visual.md` and `docs/weekly_status_update_notes.md`: you chose to keep them local. The two session-prompt files are in the working folder, untracked; the weekly notes stay only on the backup branch.
9. `scripts/check_pages_sync.sh` added (see below). The extra scratch worktree from an earlier session was removed; its branch `ui/tab-title-icon` is kept (its commit is also on `origin/feature/spoken-directions`).

## Comparison (checked 2026-11-26, after the build)

| File | Live SHA-1 (first 8) | Local | Same? |
|---|---|---|---|
| `index.html` | b041e0a2 | b041e0a2 | yes |
| `cincinnati.html` | e425c479 | e425c479 | yes |
| `oxford.html` | 0e94913c | 0e94913c | yes |
| `ask.html` | 26cce004 | 26cce004 | yes |
| `ask-standalone.html` | 9ff40a73 | 9ff40a73 | yes |
| `cincinnati_atlas.geojson` | 720d8c3b | 720d8c3b | yes |
| `oxford_atlas.geojson` | 92c6b178 | 92c6b178 | yes |
| `assistant/rules.json` | 8b2a6042 | 8b2a6042 | yes |
| `assistant/cincinnati.json` | 1a563ebb | 1a563ebb | yes |
| `assistant/oxford.json` | f65f5fb3 | f65f5fb3 | yes |
| `routing/oxford.graph.json` | 7e54916d | 7e54916d | yes |
| `google_places_enriched.geojson`, `google_place_matches.csv` | 404 | absent | yes (intended) |

The data generated date is still 2026-11-13: nothing has been re-fetched since then.

## Remaining differences between localhost and Pages

| # | Difference | Where | Cause | Evidence | Severity | Must differ? |
|---|---|---|---|---|---|---|
| 1 | Pages is `https`, localhost is `http`. Geolocation works on both (localhost counts as a secure context). It would fail on a phone opening a LAN IP such as `http://192.168.x.x` | `navigator.geolocation` in `src/atlas/web/map/*.js` | Browser rule | `isSecureContext` true on both in the first check | harmless | yes |
| 2 | Pages caches for 10 minutes (`cache-control: max-age=600`); `python3 -m http.server` sends no cache header. After a push, the live page can take up to about 10 minutes plus the build to change | live response headers | GitHub Pages CDN | `curl -I` | harmless | yes |
| 3 | `file://` does not work: the page fetches GeoJSON, the routing graph and `tts/`, which browsers block there. Always use `http://localhost`. Not tested this time | `ensureData` in the map JS | Browser rule | grep only | harmless | yes |

Things that no longer differ: the city shown by `cincinnati.html` / `oxford.html` (now the page's own city; a saved city only affects `index.html`, and a "Back to <city>" button shows when they differ), the Leaflet source (vendored, 0 `unpkg` references), the report fallback (0 `issues/new` links in the five app pages), the basemap URL (USGS Topo everywhere, tiles load on both), asset paths (all relative, so serving the repo root matches the Pages layout), the Supabase URL and publishable key (same in both), and service workers (none).

## Config and secrets

- The Supabase URL and the `sb_publishable_…` key appear in the pages and match `config/ratings.yaml`. The project allows that key to be public.
- Scan of all downloaded live files (HTML, both GeoJSON files, the assistant JSON files, the routing graph) for `service_role`, `sb_secret_`, JWT-shaped strings, `AIza…`, `ghp_…`: 0 files with hits. Not scanned: `places/`, the `tts/` model files and git history.
- Google Places data: not in `main`, 404 on Pages. It exists only in `backup/old-local-main-2026-11-26`, a local-only branch that must never be pushed.

## Things that look intentional

- Region order: `?region=` first, then the page's own city (one-city pages only), then the saved city, then position, then the city list.
- Lazy-loaded city data, vendored Leaflet, `max-age=600` on Pages, `cache: 'no-cache'` on the GeoJSON fetch.
- The static place pages under `data/map/places/` keep their GitHub "Report a problem" link (you chose to keep them; they have no in-app form). Checked on `places/cincinnati/area-history-98b07.html`: 2 links.
- The design board and prototypes are local-only (git-ignored); they live in your working folder and on the backup branch.
- DC and Dayton: everything is already on `main` (regions with the limited tier, data cards, crawl specs, sources). Nothing was left behind in the backup.

## Things that look like accidents

- None open in the repo.
- None. The scratch worktree is gone.

## Questions for you

None open.

## How to check for drift

Run `scripts/check_pages_sync.sh` from the repo. It compares 11 live files with `origin/main`, confirms the Google Places files are 404 on Pages, and re-renders the three map pages in a temporary checkout to compare with the committed ones. It writes nothing to the repo. Last run: all same, "in sync". Right after a push, wait a minute or two (build) before trusting a difference.

Workflow: work locally, check on `http://localhost`, push, wait about a minute, run the check. If the page template is touched, regenerate with `python scripts/rerender_maps.py` and `python -m atlas.assistant.page`, never `make map`.

## What I could not check

- I did not open the live site in the browser after the last push. I compared hashes, which proves it equals the code I tested on localhost (the city-page fix and the missing GitHub links were checked there, with no console errors).
- Not tested: `file://`, geolocation prompts, phone or LAN access, Oxford and the index page in the browser, map popups, the Ask panel, routing and TTS loading.
- Secrets were not scanned in `places/`, `tts/` or git history.
- 19 browser tests were skipped in the last run; I did not look into why.
- Crawler tests, run in pieces on 2026-11-26: `test_extract` 23 passed, `test_discovery` 4 passed, and every test in `test_crawler`, `_c2` and `_c3` passed (61 of 61 in those three files). Eight of them are slow (47 to 66 seconds each: conditional requests, translation copies, terms that forbid bots, and five browser-rendering tests), so a whole-file run takes many minutes. The earlier "hang" was just slowness.
- A full `make map` data rebuild was not run (it writes into the repo), so I cannot say whether re-fetching would change the data.
