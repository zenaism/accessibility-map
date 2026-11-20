# Openway Assistant: morning report (run of 2026-11-20)

Branch `feature/assistant` (worktree `accessibility-map-assistant`). Nothing pushed, merged or published. No model downloaded, no new Python dependency.

## What works
- **Pipeline**: plan -> run tools -> compose -> verify. Rules planner + template composer (guided mode, no model) and an optional local model (qwen2.5:3b via Ollama) for planning and composing, always validated and falling back to rules. Every sentence is checked by the verifier; unsupported sentences are removed, and if nothing is left the answer is "I don't know".
- **Behaviour**: emergency -> "call 911" only; refuses "ADA compliant" / "safe" / "meets ADA" questions; "I only cover Cincinnati and Oxford for now"; honest "I don't have information about X yet" for housing, voting, shelters, worship, comfort; live info (bus times, weather, open now) refused as a snapshot; events use dates in words, never show past events, always say when the data was built (13 Nov 2026) and that it is a snapshot; at most one clarifying question; restrooms OpenStreetMap marks private are left out; planted instructions in records are treated as data (tested).
- **Interface**: chat web component (`src/atlas/web/assistant/`): answer cards, quick-ask tiles, Sources, More detail, Read aloud (pause/speed/stop), Show on map, Route here, Call, Report a problem, plain-language mode, text size, My needs (3 optional questions, localStorage in try/catch), voice input, photo questions, live-region announcements, keyboard use, phone/tablet/desktop layouts, colour theme.
- **Pages**: `/ask.html` (own page), a header "Ask" panel on the map pages, and `data/map/ask-standalone.html` (one 1 MB file with the data inside; opens from email or any static host; guided mode only).

## Start it
```
cd /Users/mariamzenaishvili/code/research/accessibility-map-assistant
scripts/serve_assistant.sh              # port 8002; prints the URLs
```
- http://localhost:8002/ask.html (chat page), http://localhost:8002/oxford.html and /cincinnati.html (map with the "Ask" panel).
- Guided mode needs no model. For "Local model": start Ollama (`ollama serve`, qwen2.5:3b installed), open Settings -> Local model. Photo questions also need llava-phi3.
- Terminal: `source env.sh; python -m atlas.assistant.chat_cli --today 2026-11-20 "Does the Art Museum lend wheelchairs?"` (`--model` for the model).
- `env.sh` is untracked (sets PATH to the main checkout's venv, PYTHONPATH, ATLAS_* dirs).

## 10 questions to try
1. Where is the closest accessible restroom near downtown?
2. Does the Art Museum lend wheelchairs?
3. What's on this weekend in Oxford?
4. Any audio described shows next Saturday?
5. Find food with no steps near OTR (also try My needs -> "No steps")
6. How do I get to the Cincinnati Art Museum without steps?
7. Is Music Hall ADA compliant?
8. Where is accessible housing near Oxford?
9. Is Mt. Adams too steep to roll around?
10. I need an ambulance  (and: Where can I see a waterfall without stairs? for an honest unknown)

## Tests (exact results)
- Full `pytest -q`: **331 passed**, 7 warnings, 11 min 38 s (includes the crawler tests). No failures. I did not compare with main.
- `node --test`: **90 of 90** golden parity cases pass (JavaScript reproduces Python plans, answer text, cards).
- Assistant tests alone: 111 (dates, verifier, planner, executor, composer, engine, server, export, 29 Playwright UI tests including axe-core on 7 states: no violations; keyboard-only, phone and 320 px widths, localStorage blocked, voice/photo states, hooks).
- `ruff check` / `ruff format --check` clean on all files I added. (The repo has older E501 errors in other scripts; untouched.)

## Evaluation (`eval/results/agent_2026-11-20.md`, `..._A_rerun.md`)
174 questions: 44 bank, 55 new, 57 category (unlabelled), 18 traps. A ran on all; B, C, D on a sample of 44 (every 6th plus all traps) because a model answer takes 5 to 25 s (one D answer stalled for 1120 s when the machine was loaded).
| | A rules+templates | B model plan | C model compose | D both |
|---|---|---|---|---|
| tool = bank tool (bank, sample 8 for B-D) | 34/44 (77%); any lookup tool 44/44 | 8/8 | 8/8 | 8/8 |
| retrieval@5 | 39/45 (87%) | 6/8 | 7/8 | 6/8 |
| honesty (unknown vs answer) | 46/54 (85%) | 8/10 | 9/10 | 9/10 |
| traps | **18/18** after fixing my checker (15/18 in the first run: the checker counted the refusal's own words) | 13/18* | 15/18* | 13/18* |
| verified, none removed | 171/174 | 43/44 | 36/44 | 38/44 |
| median seconds | 0.05 | 5.9 | 10.5 | 23.1 |
*B-D trap numbers were scored with the old checker and are understated by the same false failures; not re-run (about 1 h).
Finding: the model adds time (100x to 400x) and removes more sentences (C: 9, D: 6) and did not beat rules. In a hand check, model sentences were grounded but sometimes off topic (the verifier does not test relevance). Rules + templates (A) is the one to ship.
Limits: 3B model, one machine, one date, small B-D samples, answer key written after seeing the data and not checked by people, no human check of groundedness. Memory: eval process 0.38 GB; qwen2.5:3b 2.3 to 2.4 GB resident.

## NOT checked
Real screen reader (VoiceOver/TalkBack/NVDA), real phone or tablet, real microphone (voice tested with a fake), real speech output (tested with a fake), real users, other browsers than Chromium, the model photo answer quality (llava-phi3 path exists; tested with a stubbed server), 200% browser zoom (only 320 px width and big-text setting), forced-colours mode visually, reading level of answers, the routing Claude's `window.AtlasRouting`.

## Known problems
- Some Miami events have starts between 00:00 and 05:59 that look like UTC; I hide those times but the date may be a day off ("Friday Public Skate" listed Saturday).
- Rating "accessible/partial" comes from the map; old sources are shown with their age but conflicting sources are only shown side by side on the card.
- Fuzzy matching is my own (not rapidfuzz) so the browser can run the same algorithm; unusual spellings of place names may miss.
- Guided mode cannot compute routes from the user's location or area conditions for arbitrary points (precomputed per place and named area only).
- Model planner rejected 20 of 58 plans (fell back to rules); "how do I roll to the zoo" went to search instead of route.
- Findlay Market is not a place in the data, so "Does Findlay Market have an accessible restroom?" says it has nothing (scored a gap, correct), but the bank counted it as honest=false in A because the answer lists other restrooms; see eval file.
- Machine was loaded; timings are indicative.

## Decisions I made
- No pydantic/fastapi: dataclasses + stdlib `http.server` with server-sent events.
- Own fuzzy matcher instead of rapidfuzz (same algorithm in JS).
- All vocabulary as data in `rules.py` exported to `rules.json`; algorithms written twice, kept equal by 90 golden cases.
- Model never writes facts: it fills slots (validated, turned into a canonical question for the rules planner) or writes two headline sentences that the verifier checks; safety/trust/no-data/live questions never go to the model.
- "next Saturday" = that weekday in the following calendar week; the answer shows the resolved date.
- Weekend = Saturday + Sunday; today is injectable (`?today=YYYY-MM-DD` in the page).
- Tiles/map hooks: window events are cancelable; handler calls `preventDefault()` to say "handled"; otherwise the chat falls back to opening the map page.
- Coordinates are stripped from the streamed plan and never logged; the server logs no bodies.
- Exported data (515 KB + 332 KB + 19 KB) is committed; `ask-standalone.html` (about 1 MB) too.
- Mockup gate waived: built the interface directly, saved 26 screenshots in `docs/work_logs/screens/assistant/` (taken before the colour theme; tablet and phone checked after).

## Hooks the integrator needs
- `atlas:show-places` {ids}, `atlas:route-to` {placeId, profile}, `atlas:open-report` {text}: implemented in `map_viewer.py` between `ASSISTANT START/END` markers (placeholders `__ASSISTANT_JS__`, `__ASSISTANT_CSS__`, `ASSIST_IDS` filter in `current()`). `route-to`: returns early when `window.AtlasRouting` exists (routing must call `preventDefault()` itself); otherwise uses the saved route or Google Maps.
- Re-render maps with `python scripts/rerender_maps.py`; rebuild assistant data with `python -m atlas.export_assistant_data`, pages with `python -m atlas.assistant.page`, goldens with `python scripts/make_assistant_golden.py` (after any data refresh).
- Not edited (yours): docs/README.md, architecture.md, Makefile, progress_log.md. Suggested make targets: `assistant-data`, `assistant-page`.
- To publish: merge to the branch GitHub Pages deploys; the chat is then at `.../data/map/ask.html`. Guided mode works for everyone; the local model and photo questions only run on a computer with Ollama.
