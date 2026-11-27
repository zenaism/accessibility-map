#!/usr/bin/env bash
# Check that the live GitHub Pages site equals origin/main, and that the committed
# map pages equal what the generator produces now. Read-only: writes only to a temp folder.
# Usage: scripts/check_pages_sync.sh        (run from anywhere inside the repo)
set -u
BASE="https://zenaism.github.io/accessibility-map/data/map"
cd "$(git rev-parse --show-toplevel)" || exit 2
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
bad=0

git fetch -q origin main || { echo "could not fetch origin"; exit 2; }
echo "local main:  $(git rev-parse --short main)"
echo "origin/main: $(git rev-parse --short origin/main)"
[ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ] || { echo "  DIFFERENT: local main and origin/main are not the same commit"; bad=1; }

FILES="data/map/index.html data/map/cincinnati.html data/map/oxford.html data/map/ask.html data/map/ask-standalone.html
data/map/cincinnati_atlas.geojson data/map/oxford_atlas.geojson
data/map/assistant/rules.json data/map/assistant/cincinnati.json data/map/assistant/oxford.json
data/map/routing/oxford.graph.json"

echo; echo "1. Live Pages vs origin/main (Pages can lag the push by about a minute, and caches 10 minutes)"
for f in $FILES; do
  git show "origin/main:$f" 2>/dev/null | shasum | cut -c1-8 > "$TMP/want"
  if ! curl -fsS "$BASE/${f#data/map/}" 2>/dev/null | shasum | cut -c1-8 > "$TMP/got"; then :; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/${f#data/map/}")
  [ "$code" = 200 ] || { echo "  FAIL  $f  (HTTP $code)"; bad=1; continue; }
  if [ "$(cat "$TMP/want")" = "$(cat "$TMP/got")" ]; then echo "  same  $f"; else echo "  DIFF  $f  (origin $(cat "$TMP/want"), live $(cat "$TMP/got"))"; bad=1; fi
done
for f in google_places_enriched.geojson google_place_matches.csv; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/$f")
  [ "$code" = 404 ] && echo "  ok    $f is not published (404)" || { echo "  FAIL  $f answers HTTP $code, Google Places data must never be public"; bad=1; }
done

echo; echo "2. Committed pages vs a fresh render (done in a temporary checkout, nothing is written to your repo)"
WT="$TMP/wt"; REPO="$(pwd)"
if git worktree add -q --detach "$WT" origin/main 2>/dev/null; then
  ( cd "$WT" && PYTHONPATH=src "$REPO/$PY" -B scripts/rerender_maps.py >/dev/null 2>&1 ) || echo "  (render step reported an error)"
  for f in data/map/index.html data/map/cincinnati.html data/map/oxford.html; do
    if git show "origin/main:$f" | cmp -s - "$WT/$f"; then echo "  same  $f"; else echo "  DIFF  $f is out of date with the generator (run: python scripts/rerender_maps.py)"; bad=1; fi
  done
  git worktree remove --force "$WT"
else
  echo "  could not make a temporary checkout; skipped"
fi

echo
[ $bad = 0 ] && echo "RESULT: in sync" || echo "RESULT: differences found (see above)"
exit $bad
