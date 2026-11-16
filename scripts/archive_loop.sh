#!/bin/bash
# Archive weather, weather alerts and transit alerts for every region, once an hour, until stopped.
#   nohup scripts/archive_loop.sh > /dev/null 2>&1 &      start it (it stops when the computer sleeps or restarts)
#   pkill -f archive_loop.sh                               stop it
# For a permanent schedule use cron instead (crontab -e):  7 * * * *  cd /path/to/accessibility-map && .venv/bin/python -m atlas.cli archive all --region all
cd "$(dirname "$0")/.."
while true; do
  .venv/bin/python -W ignore -m atlas.cli archive all --region all >> data/history/archive.log 2>&1
  sleep 3600
done
