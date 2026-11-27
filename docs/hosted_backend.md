# Hosted backend for the assistant (trial)

Status: **trial running on a shared university Linux server since 2026-11-26 (real model calls checked through the public address); not used by the public page yet.** Decision: [D-104](decisions.md). Diagram: [`architecture.md`](architecture.md) section 21.

The public chat page answers in guided mode (rules and templates, in the browser). This adds an optional **online model** for free-text questions: the page calls our assistant server on a shared Linux machine, and that server calls a hosted model through OpenRouter. It is a first, simple setup that can move to any other host.

## What runs where

| Piece | Where | Does |
| --- | --- | --- |
| Chat page | the static site (or `localhost`) | sends the question to the server named in `OPENWAY_SERVER_BASE` when the person picks "Online model" in Settings |
| `deploy/shared_server/openway.cgi` | the shared machine's web space (`~/public_html/cgi-bin/`) | front door with HTTPS: passes `/api/health` and `/api/ask` to the assistant server on the same machine. Holds no key. |
| `atlas.assistant.server` | the same machine, started by `deploy/shared_server/run.sh` as the project owner | the unchanged pipeline (plan, run tools, compose, verify); two short model calls per question |
| OpenRouter | outside | forwards the two calls to the model in `OPENWAY_CLOUD_MODEL` |

Why a front door plus a server: on a shared machine the web server runs every user's scripts as one shared account, so a script cannot keep a private key. The key stays with the assistant server, which runs as the project owner.

## What leaves the device

- **To our server:** the question, the city, the "My needs" choices and, if shared, the location. The tools need them. Nothing is written to disk or logged.
- **To the model service:** the message, the last six turns of this chat (each cut to 400 characters) and the place records the tools found. Never the location, the needs or saved places (D-43).
- Guided mode is unchanged and sends nothing anywhere. Settings says which mode is on.

## How the model is used (D-105)

One model call per message decides: **lookup** (slots, checked, then the normal plan, tools, cards and sources) or **talk** (a short reply in the assistant's own words, shown without cards and labelled "Assistant · not from the map data"). When a lookup finds places, a second call writes the main sentence about the first one. Safety and trust messages never reach the model. The persona and the rules it follows are `PERSONA` and `PLAN_SYSTEM` in `src/atlas/assistant/llm.py`. Picture: [`architecture.md`](architecture.md) section 21.

To see what happened for a message, open the browser console: lines starting with `[Openway]` say whether a model was called and which steps it did. They never contain the message or the answer.

## Limits and failure

- Per visitor: `OPENWAY_RATE_PER_HOUR` (30). Everyone: `OPENWAY_RATE_PER_DAY` (600). Over a limit, or when the model fails or is slow, the answer comes from guided mode.
- Set a monthly dollar limit on the OpenRouter key as well. That is the real cap on spending.
- Only the sites in `OPENWAY_ALLOW_ORIGINS` may call the API from a browser.
- Photos are not accepted (no vision model here).
- Other users of the shared machine can reach the server's local port and use the model within the limits. They cannot read the key.

## Install on a shared machine (no root)

```bash
# 1. code, data and Python packages in the home directory
uv venv --python /usr/bin/python3 .venv
uv pip install -e . duckdb pandas rapidfuzz networkx scipy
make kb                                   # or copy data/kb/atlas.duckdb

# 2. settings and key
cp deploy/shared_server/env.example deploy/shared_server/env    # edit the allowed sites
mkdir -p ~/.config/openway && chmod 700 ~/.config/openway
# put the OpenRouter key in ~/.config/openway/openrouter.key, then: chmod 600 on it and on env

# 3. start, and keep it running after a restart
deploy/shared_server/run.sh
crontab -e     # add the two lines shown at the top of run.sh

# 4. front door
mkdir -p ~/public_html/cgi-bin
cp deploy/shared_server/openway.cgi ~/public_html/cgi-bin/ && chmod 755 ~/public_html/cgi-bin/openway.cgi
```

Check: `https://<host>/~<user>/cgi-bin/openway.cgi/api/health` returns `"hosted": true, "model": true`.

Point a page at it: `OPENWAY_SERVER_BASE=https://<host>/~<user>/cgi-bin/openway.cgi python -m atlas.assistant.page`. Without that variable the page is built exactly as before.

## Moving to another host

Only two things are host-specific: the front-door script and the settings file. On a host that can run a web service directly, drop the script, run `atlas.assistant.server` behind that host's HTTPS, and change `OPENWAY_SERVER_BASE`. To use a local model instead, set `OPENWAY_PROVIDER=ollama`.
