---
name: accessibility-map
description: Project guide for the Accessibility Map repo (wheelchair accessibility data fusion and assistant). Use when working on data collection, sources, schema, docs, maps or the assistant here: it gives the goal, the doc map, the working rules and where to record decisions and diagrams.
---

# Accessibility Map: project guide

## What this project is
A multimodal data-fusion layer and assistant for wheelchair users, started for Cincinnati and Oxford, Ohio, now being extended to Maryland, DC, Dayton and eventually the whole US. The maps are a visualization; the product is the dataset plus the assistant. Another lab team will consume the data in their own accessibility app, so formats and schema must stay stable and documented. Reference predecessor: MU-Smart/Accessibility-Assistant (NYC, Manhattan).

## Where things are (read these first)
- `docs/system_overview.md`: START HERE. Whole system, rating scheme, pros and cons, comparison.
- `docs/README.md`: index of every doc and which doc owns which topic. Edit the owner, do not repeat content elsewhere.
- `docs/national_data_plan.md`: the plan for automated, nationwide collection (draft until approved).
- `docs/architecture.md`: Mermaid diagrams of the system.
- `docs/source_types.md`: which kinds of sources beyond government, with licences.
- `docs/decisions.md`: decision log (what, why, alternatives, costs).
- `docs/data_landscape.md` section 1: the single attribute list (what users need).
- `config/categories.yaml`: every question category and how to fetch it (docs/categories.md is generated: `python scripts/make_categories_doc.py`). Add or change categories there.
- Source tracker: `docs/source_inventory.md` and `data/source_inventory.csv` refresh automatically after every `atlas fetch`; `data/ledger/fetch_log.jsonl` is the append-only fetch history. Do not edit them by hand.
- `SOURCES.md`: status of each source (collected, next, idea). `config/sources.yaml` and `config/regions.yaml`: the registry the pipeline reads.
- `src/atlas/`: connectors, export, map, assistant (DuckDB knowledge base in `assistant/kb.py`). Commands: `make map`, `make kb`, `make inventory`, `make test`.

## Working rules
1. **Explain with pictures.** The user learns the system from diagrams. Any design proposal or change to the architecture gets a Mermaid diagram (add or update it in `docs/architecture.md`). Colour key: green = exists, blue = planned, grey = external. Keep labels plain words; avoid colons and parentheses in sequence-diagram aliases.
2. **Record the why.** When something non-obvious is decided (tool, format, source, policy), add a numbered entry at the top of `docs/decisions.md` with decision, why, alternatives, costs/revisit, and a Basis line saying *recorded* (written somewhere) or *inferred* (reconstructed, needs confirming). Never present guessed reasoning as the user's.
3. **No duplicate docs.** Check `docs/README.md` for the owner before writing; link instead of copying. Update the index when adding a doc.
4. **Plan doc.** The Claude Doc "Data & RAG Implementation Plan" has a "Progress and to-do" section; after a chunk of work, add a Done row there and mirror it in `docs/progress_log.md`.
5. **Discover automatically, rate automatically.** Do not hand-pick sources for new regions: use the discovery routes in the national plan; the trust engine rates each candidate automatically (no one can hand-check data); see `docs/system_overview.md` section 4. Show uncertainty: confirmed, reported, unknown.
6. **Provenance on every fact:** source URL, retrieval date, verbatim quote or page/region, method, confidence, licence. Raw files are immutable.
7. **Budget is $0 for now.** Design and build with free data, free tools and local models; never assume a paid API (search, LLM, vision, hosting). Rules and filters first, models last, cache by content hash. See `docs/national_data_plan.md` section 0.1.
8. **Licences:** Google Places and Yelp are live lookups and evaluation only, never stored. Check terms before redistributing anything (OSM ODbL, CC BY-SA imagery, etc.).

## Repo conventions
- Commit as Mariam Zenaishvili <zenaism@miamioh.edu>; no AI co-author lines. Work on `main`; push directly.
- The repo is public: review docs for private details (names, unpublished results, keys) before committing.
- A global gitleaks pre-commit hook blocks secrets; never bypass with `--no-verify`. Only `sb_publishable_` Supabase keys may be in the repo; never `sb_secret_` or `service_role`.
- Basemap is USGS The National Map only (OSM tile servers block this use; CARTO needs a key).
- Style: minimal, modern, works on phone and tablet, list-first and screen-reader friendly (blind and wheelchair users).
- Pages: `https://zenaism.github.io/accessibility-map/data/map/{cincinnati,oxford}.html`; rebuild with `make map`, push, wait about a minute. Rebuilding can change many data files; check `git diff --stat` before committing.
- The local folder and repo are named `accessibility-map`; the Python package is still `atlas`.

## Adding a region or source (target workflow)
1. Add the region (resolve Census FIPS and pin the OSM relation; never match by name).
2. Run discovery (catalogs, gov crawl, place-driven pages, templated search), review candidates.
3. Fetch to the raw store, extract (text, PDF, OCR, vision), normalize to entities and observations, fuse.
4. Produce the release and the coverage report; update `SOURCES.md`, `docs/progress_log.md` and, if a choice was made, `docs/decisions.md`.
