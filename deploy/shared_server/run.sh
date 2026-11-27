#!/usr/bin/env bash
# Start the Openway Assistant server on a shared Linux machine, if it is not already running.
# No root needed. Safe to call again and again, so cron can keep it up:
#   @reboot       $HOME/accessibility-map/deploy/shared_server/run.sh
#   */10 * * * *  $HOME/accessibility-map/deploy/shared_server/run.sh
# Settings come from deploy/shared_server/env (copy env.example; that file is private and not in git).
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f deploy/shared_server/env ] && . deploy/shared_server/env
PORT="${PORT:-18002}"
PY="${PYTHON:-.venv/bin/python}"
if pgrep -u "$(id -u)" -f "atlas.assistant.server --port $PORT" >/dev/null; then exit 0; fi
export OPENWAY_PROVIDER OPENWAY_KEY_FILE OPENWAY_CLOUD_MODEL OPENWAY_ALLOW_ORIGINS OPENWAY_RATE_PER_HOUR OPENWAY_RATE_PER_DAY OPENWAY_SERVER_BASE
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
[ -f data/kb/atlas.duckdb ] || "$PY" -m atlas.assistant.kb
mkdir -p "$HOME/.local/state/openway"
nohup "$PY" -m atlas.assistant.server --port "$PORT" >"$HOME/.local/state/openway/server.log" 2>&1 &
echo "started on port $PORT"
