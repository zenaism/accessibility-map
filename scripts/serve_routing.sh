#!/bin/bash
# Serve the map pages and routing graphs over HTTP (browsers cannot fetch the graph from file://).
# Usage: scripts/serve_routing.sh [port]    Stop with Ctrl-C. Listens on localhost only.
cd "$(dirname "$0")/.." || exit 1
PORT="${1:-8001}"
echo "Oxford map: http://localhost:${PORT}/oxford.html"
exec "${PYTHON:-python3}" -m http.server "$PORT" --bind 127.0.0.1 --directory data/map
