#!/usr/bin/env bash
# One command: start the Openway Assistant on http://localhost:8002 (chat page, both maps, the local /api/ask).
# Guided mode needs no model. For "Local model" mode, start Ollama first (ollama serve) with qwen2.5:3b installed.
#   scripts/serve_assistant.sh            # port 8002
#   PORT=8010 scripts/serve_assistant.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=/Users/mariamzenaishvili/code/research/accessibility-map/.venv/bin/python
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
[ -f data/kb/atlas.duckdb ] || "$PY" -m atlas.assistant.kb
[ -f data/map/assistant/rules.json ] || "$PY" -m atlas.export_assistant_data
exec "$PY" -m atlas.assistant.server --port "${PORT:-8002}"
