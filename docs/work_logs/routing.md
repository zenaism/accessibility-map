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
