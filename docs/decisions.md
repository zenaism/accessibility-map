# Decision log

Every significant choice, with the reasoning, the alternatives we considered and what it costs us. Newest first. Add an entry whenever we decide something non-obvious (a tool, a format, a source, a policy).

**How to read the "Basis" line.** *Recorded* means the reason is written somewhere in the repo (linked). *Inferred* means the decision is real but its reasoning was never written down; I reconstructed the likely reasons from the code and design, and they need a quick confirm or correction from you.

**Template**

```
### D-NN: Title (date, status)
Decision: what we chose.
Why: the reasons.
Alternatives: what else we considered and why not.
Costs / revisit if: what this makes harder, and what would make us reconsider.
Basis: recorded (where) | inferred (confirm)
```

Status is one of: accepted, proposed (not yet approved), superseded.

---

### D-21: Parameters set by the user's answers (2026-11-15, accepted)
**Decision:** (1) **Coverage is the whole city**, not selected places: a region such as Washington DC is collected completely, and Maryland starts from whole cities and counties. (2) **Outages and personal routes** are the predictions that matter most; missing-attribute filling and source reliability follow. (3) **Files are acceptable to the other team:** versioned Parquet plus a DuckDB file, monthly updates unless they ask otherwise. (4) **Everything runs on the user's computer for now** (no lab GPU assumed); Zenodo is the likely free home for raw archives; no WARC files for now. (5) Keep **all raw history** for the two target regions and thin old snapshots later. (6) **Scrapy first** with a custom fallback; crawler saves images and documents from **relevant pages only** at first. (7) Rating **tiers 80 / 50 / 30 accepted**; build the **calibration set** of about 100 facts from official data; **licensing:** facts and short quotes with links, full page copies private. (8) **Reddit is in scope** (changes my recommendation): needs research API access and strict handling. (9) **Mapillary street imagery is used if possible** (after a licence review: share-alike). (10) **User profile and feedback only after ethics review.**
**Why:** these are the user's own answers to the open questions; items 8 and 9 override my first recommendation (first release without them) because the user wants lived-experience data and imagery.
**Alternatives:** none: the user decided. Defaults used where the user left a question blank: skip and ask permission for sites whose terms forbid bots (C2); ask counsel before redistributing page-derived data (E3).
**Costs / revisit if:** laptop-only limits OCR and vision work (small batches, small models); Reddit needs approval and credentials and brings terms and privacy duties; Mapillary imagery is CC BY-SA, so derived data may carry share-alike duties; whole-city coverage raises crawl and storage needs. Revisit when a lab GPU or storage appears, and after the Reddit and Mapillary access steps.
**Basis:** recorded (`questions_for_you.md`, answers dated 2026-11-15).

### D-20: Build the crawler on Scrapy plus our own modules; decide after a spike (2026-11-15, proposed)
**Decision:** the web crawler uses Scrapy as the crawl engine (queue, politeness, retries, resume, sitemaps) with Playwright for JavaScript pages, and our own modules for what is specific to us: place-driven seeds, relevance scoring and budgets, completeness gates, provenance and extraction hand-off. A 2 to 3 day spike (phase C0) confirms it; if Scrapy cannot keep our priority queue, resume after a kill, and apply the same politeness limits to browser pages, we build a small custom async crawler instead. We crawl wide (save everything in scope) and extract deep (read only what looks relevant).
**Why:** the hard, easy-to-get-wrong parts of a polite, resumable crawler are already solved in Scrapy; our time is better spent on the parts nobody else builds. Saving everything in scope lets future questions be answered without re-crawling, and relevance steering keeps a country-wide crawl affordable at $0.
**Alternatives:** extend the current `web.py` (we would rewrite every hard part ourselves); Crawlee for Python (younger Python port); Crawl4AI (opinionated, adaptive mode but less control); Browsertrix Crawler (good WARC archiver, AGPL, Docker, weak custom logic: kept as an optional later add-on); fully custom (most control, most effort: the fallback).
**Costs / revisit if:** Scrapy's event loop and learning curve; the browser add-on's maintenance is unchecked; revisit after the spike and again if the add-on lags the Playwright version we need.
**Basis:** recorded (research and plan in `crawler_plan.md`, 2026-11-15); tool claims are mostly vendor-sourced and unchecked, which is why the spike comes first.
**Update 2026-11-15 (spike result):** Scrapy 2.20 handled all three spike conditions in tests on a local trap website: our priority scoring drives the queue (best-first under a small budget), a killed crawl resumes from the on-disk queue with no repeats, and the per-host politeness limits and Retry-After pauses apply to every request. Decision: **accepted, build on Scrapy.** Not yet tested: Playwright pages inside the same limits (phase C2).

### D-19: Schema v2 is added by an upgrade step; trust scores come from measured parts only (2026-11-15, accepted)
**Decision:** observation schema v2 (history, confidence, method, evidence) is produced by `schema.upgrade()` from the v1 tables the connectors already write, instead of changing every connector. Source ratings are computed by `trust.py` from components we can actually measure today (authority, provenance, freshness, completeness, quality); agreement and track record stay empty until fusion and reference data exist, and the remaining weights are rescaled. An unknown or unclear licence caps a source at tier B (usable, not redistributable).
**Why:** nothing breaks (80+ tests keep passing, existing data stays valid); we can reprocess old data into v2 and ship it. Counting unmeasured components as zero would unfairly sink every source, and counting them as full would invent evidence. Licence is a legal limit, not a quality score, so it caps the tier.
**Alternatives:** change all connectors to write v2 (bigger change, risky now); fill unmeasured components with a default (false precision).
**Costs / revisit if:** scores barely separate sources until agreement and track record exist (36 of 46 collected sources are tier A today); the weights are guesses. Revisit after the fusion step and the first reference-data comparison.
**Basis:** recorded (built and tested in this session: `src/atlas/schema.py`, `trust.py`, `cards.py`, `candidates.py`, `tests/test_phase0.py`).

### D-18: Question categories and source tracking live in code and update themselves (2026-11-15, accepted)
**Decision:** (1) `config/categories.yaml` is the single list of what wheelchair users ask about (trails, parking, restrooms, events, and so on), with the OSM selectors, Overture hints, attributes, page keywords, source kinds and refresh rates to fetch each; `docs/categories.md` is generated from it and checked against `config/attributes.yaml`. (2) Every `atlas fetch` appends a line to `data/ledger/fetch_log.jsonl` (source, region, time, ok or error) and refreshes `docs/source_inventory.md` and `data/source_inventory.csv`, which now include each source's URL and licence.
**Why:** the user wants the category list reused for later data fetching and wants the list of sources tracked without manual upkeep. Generated docs cannot drift from the config; the ledger is also the history needed in D-17.
**Alternatives:** a hand-written category doc and source list (drift, forgotten updates); a database table for the ledger (more moving parts for a small log).
**Costs / revisit if:** the inventory rewrites its whole table on each fetch (fine at this size); the OSM and Overture hints are a starting point and Overture names are unchecked.
**Basis:** recorded (user request, this session; `src/atlas/cli.py`, `src/atlas/inventory.py`, `scripts/make_categories_doc.py`).

### D-17: Keep history from day one (2026-11-15, proposed)
**Decision:** never overwrite data. Every observation carries `observed_at`, `valid_from`, `valid_to` and its source snapshot; a change adds a row. Archive real-time and fast-changing sources (GTFS-Realtime, weather, 311, key web pages) on a schedule, and keep every extraction run (model, prompt version, output).
**Why:** predictions (missing attributes, repair risk, outages, source reliability) and trends need what changed and when, and that history cannot be rebuilt later. Storing it costs little now.
**Alternatives:** keep only the latest value (smaller, but forecasting and "last confirmed" are impossible); archive only on demand (misses what we did not know we needed).
**Costs / revisit if:** more disk and a more careful schema; hourly feeds across many regions can grow fast, so thin or compress old snapshots if space runs out.
**Basis:** recorded (user request to plan for future computing and prediction, this session; `data_needs.md` section 3).

### D-16: Rate sources and facts automatically; no manual review (2026-11-15, proposed)
**Decision:** a trust engine scores each source (0 to 100: authority, provenance, freshness, completeness, internal quality, cross-source agreement, track record) and each fact (source score x extraction reliability x freshness x corroboration - conflicts). Sources are accepted automatically (Tier A, B), quarantined (C) or rejected (D). The assistant shows facts as confirmed, reported or unknown.
**Why:** the user cannot hand-check data, and manual review would not scale to a country. Showing the rating keeps the assistant honest instead of treating all sources as equally true.
**Alternatives:** human approval of every source (does not scale, no one to do it); no rating at all (all sources look equally reliable, unsafe); crowd voting on facts (needs many users).
**Costs / revisit if:** the rating measures consistency, not truth, so a confidently wrong source can pass; starting weights are guesses until reference data accumulates. Revisit after the first regions: compare scores against official data and the lab's wheelchair recordings, and tighten the thresholds.
**Basis:** recorded (user request, this session; `system_overview.md` section 4). The weights and cut-offs are my proposal: confirm.

### D-15: Zero-budget design: free tools, rules first, models last (2026-11-15, accepted)
**Decision:** plan and build everything to run at $0: no paid search, LLM, vision or hosting APIs. Use rules and filters first, small local open models only on pages that pass, free OCR and PDF parsers, Playwright for JavaScript pages, caching by content hash, and free hosts (Zenodo, Hugging Face, GitHub releases) for data releases.
**Why:** the user has no budget for now. A design that needs paid APIs would stall, and cheap-first processing also makes a national crawl feasible on modest hardware.
**Alternatives:** wait for funding (blocks progress); use frontier-model APIs on free credits (not reliable at national scale and credits run out).
**Costs / revisit if:** lower extraction accuracy than frontier models, slower processing, a smaller route D (search), files instead of a live API. Revisit when funding or university compute becomes available: first upgrade the claim-extraction model, then add a search API.
**Basis:** recorded (user instruction, this session; `national_data_plan.md` section 0.1). The specific free tools and their limits are unchecked: verify before relying on them.

### D-14: A source is complete only after independent checks pass (2026-11-15, proposed)
**Decision:** every crawl ends with six completeness gates (status audit, sitemap coverage, count check, archive check, keyword audit, sample audit); failures go to a gap queue and show in the coverage report. Pages needing JavaScript are fetched with a headless browser.
**Why:** the user wants to be sure we fetch every page we might need. A crawler cannot know what it missed unless it compares itself with something independent, and silent gaps would become silent wrong answers ("unknown" would be reported as "no").
**Alternatives:** crawl to a fixed depth and trust it (cheapest, but gaps are invisible); manual spot checks only (does not scale to a country).
**Costs / revisit if:** more requests and compute (archive lookups, headless browser, audits); tune the sample size and gate thresholds after the first two regions.
**Basis:** recorded (user request, this session; `national_data_plan.md` section 3.4).

### D-13: Diagrams as Mermaid text in the docs (2026-11-15, accepted)
**Decision:** system diagrams are written in Mermaid inside `docs/architecture.md` (green = exists, blue = planned), and every new design proposal comes with one.
**Why:** the user learns the system fastest from pictures. Mermaid renders in Obsidian and on GitHub, lives in git as text so diffs show what changed, and needs no drawing tool.
**Alternatives:** exported PNGs or slides (go stale, cannot be diffed), draw.io (separate files and tool).
**Costs / revisit if:** very large diagrams get hard to lay out; split them or use a drawing tool for posters and papers.
**Basis:** recorded (user request, this session).

### D-12: Discover sources automatically, then review (2026-11-15, proposed)
**Decision:** find new sources by automated discovery (open-data catalogs, `.gov` site crawl, place-driven pages, templated search), have an LLM draft the mapping, and approve each candidate by hand before it enters a release.
**Why:** the goal is the whole country, so hand-picking sites does not scale; but fully automatic ingestion would let wrong or unlicensed data into a dataset another team builds on.
**Alternatives:** hand-picked lists (what we did for Cincinnati and Oxford; does not scale); search-engine scraping per neighbourhood (the NYC predecessor; brittle, depends on one search engine, no provenance); fully automatic with no review (fast, but errors and licence problems reach the other team).
**Costs / revisit if:** needs a review queue and someone's weekly hours; revisit auto-approval once many mappings have been accepted without edits.
**Basis:** recorded (`national_data_plan.md`, sections 1 and 3).

### D-11: Repo name `accessibility-map`, no place name (2026-11-15, accepted)
**Decision:** rename `ohio-access-atlas` to `accessibility-map`; titles and docs describe Cincinnati and Oxford as current coverage, not the scope.
**Why:** the goal is national coverage, and "Ohio" and "Atlas" misdescribe the project. "Map" says what exists today; the assistant can grow under the same name.
**Alternatives:** `access-atlas` (smaller rename but still vague), `accessibility-assistant` (premature: the map is what exists), `accessible-places`.
**Costs / revisit if:** old Pages URLs stopped working (GitHub redirects the repo URL, not Pages). The Python package is still `atlas` and files still say `_atlas`; rename later only if worth the churn.
**Basis:** recorded (this session).

### D-10: Commits authored with the university email (2026-11-11, accepted)
**Decision:** all commits are `Mariam Zenaishvili <zenaism@miamioh.edu>`, with no AI co-author lines. History was rewritten on 2026-11-11 to enforce this. On 2026-11-15 we checked that GitHub links all 54 commits to the `zenaism` account and kept the miamioh email (rather than the private noreply address).
**Why:** the work is a Miami University research project and should be attributed to the researcher; the email is already linked to the account.
**Alternatives:** GitHub noreply address (keeps the university email out of public history; declined).
**Costs / revisit if:** the email is public in history; revisit if privacy matters more, but that means rewriting history and force-pushing again.
**Basis:** recorded (project memory, 2026-11-11 and 2026-11-15).

### D-09: Visitor ratings in Supabase, with only public keys in the repo (2026-11-12, accepted)
**Decision:** the map's one-tap accessibility ratings are stored in a Supabase project; the repo contains only the public URL and publishable key. Secret and `service_role` keys are never committed. The repo's `.gitleaks.toml` allows only `sb_publishable_` keys.
**Why:** the maps are static pages on GitHub Pages, so they have no server. Supabase gives a hosted database with row-level security reachable straight from the browser, with no server for us to run. A publishable key is safe to expose when row-level security limits what it can do.
**Alternatives:** running our own API (more to maintain), a form that creates GitHub issues (slow, needs a GitHub account), a spreadsheet backend (weak access control).
**Costs / revisit if:** depends on an external service and its free tier; abuse and spam need rate limits and moderation; ratings are crowd data and must stay labelled as such.
**Basis:** recorded (`config/ratings.yaml`, `supabase/ratings.sql`, project memory); the alternatives are inferred (confirm).

### D-08: Google Places and Yelp are live lookups and an evaluation check, not stored data (2026-11-11, accepted)
**Decision:** Google details are fetched in the browser when a place is selected, and only matched Place IDs are published. Google and Yelp are not part of the stored corpus.
**Why:** their terms do not allow keeping a permanent copy, so storing them would block us from sharing the dataset with the other lab team. They are still valuable as a comparison to measure how good our own data is.
**Alternatives:** store the details (breaks terms); leave Google out entirely (loses a useful comparison).
**Costs / revisit if:** the maps need a browser API key; it must be restricted to the site's HTTP referrer and never be a server key. Revisit if a research licence is granted.
**Basis:** recorded (`progress_log.md`, README).

### D-07: USGS The National Map as the only basemap (2026-11-12, accepted)
**Decision:** maps use the USGS basemap with the credit line USGS asks for.
**Why:** it is public domain. OpenStreetMap's volunteer tile servers do not allow this kind of use, and CARTO's free tiles now need a key.
**Alternatives:** OSM tiles (policy), CARTO (needs a key), Google tiles (terms, cost).
**Costs / revisit if:** less polished than commercial tiles. Revisit if we need a style that shows more detail at street level.
**Basis:** recorded (project memory; commit `8ef14da`).

### D-06: The map is GeoJSON files plus static pages (2026-11-11, accepted)
**Decision:** maps are generated GeoJSON and static HTML (Leaflet), committed to git and served by GitHub Pages; every place also gets a plain text page.
**Why:** no server to run or pay for; the data and the page always match; and the text pages work with screen readers, which matters for blind and wheelchair users.
**Alternatives:** a map server or vector tiles (too heavy for this size), a web framework (more to maintain).
**Costs / revisit if:** all data ships to the browser, so it will not scale to the whole country. For national scale the map should load per region or from vector tiles (see D-12 and the national plan).
**Basis:** recorded (`progress_log.md`: "Map: GeoJSON only for now"); the scaling note is inferred.

### D-05: DuckDB as the assistant's knowledge base (2026-11-12, accepted)
**Decision:** the assistant reads one DuckDB file (`data/kb/atlas.duckdb`) built from the published map data, with tables `places`, `facts` and `events`.
**Why:**
- *Right kind of questions.* "Nearest accessible restroom" needs a location filter and a distance sort, which vector search alone cannot do (recorded in `assistant_design.md`). DuckDB handles filters, joins and distance, and its spatial extension covers geometry.
- *Zero setup.* It is a single file that runs inside Python, with no database server to install or keep running, so a student can rebuild the whole thing with `make kb`.
- *Fits our data.* It reads Parquet and GeoJSON directly, matching how we store data (D-04).
- *Same data as the map.* Built from the map files, so the assistant answers from exactly what the map shows, and every fact keeps its quote and source.
**Alternatives:** PostgreSQL/PostGIS (stronger for many users writing at once, but needs a server and admin); SQLite/SpatiaLite (also single-file, but weaker for analytics and Parquet); a vector database only (cannot do distance and exact filters); a graph database (no clear gain for this data).
**Costs / revisit if:** one writer at a time and not built for many concurrent users. If the other team's app needs live multi-user queries, or the whole country makes the file very large, move serving to PostGIS (or a read-only API over DuckDB) while keeping DuckDB for analysis.
**Basis:** the "right kind of questions" reason is recorded (`assistant_design.md`, `src/atlas/assistant/kb.py`); the other reasons and the alternatives are inferred (confirm).

### D-04: Parquet and GeoParquet for stored data (2026-11-11, accepted)
**Decision:** processed data is Parquet (GeoParquet for geometry) in `data/processed/<region>/`; documents also as JSON Lines for the text index. The small map outputs stay as GeoJSON in git.
**Why:** compact, typed, and readable from Python, R, DuckDB and QGIS without our code, which matters because another team will use the data.
**Alternatives:** CSV (loses types and geometry), GeoJSON for everything (large, slow), a database dump (needs the same database).
**Costs / revisit if:** not human-readable in a text editor; GeoJSON exports remain for small layers.
**Basis:** recorded (`data_design.md`); reasons partly inferred (confirm).

### D-03: Entities plus observations, with provenance on every fact (2026-11-07, accepted)
**Decision:** everything is stored as entities (places, path segments, ramps, stops) and observations `(entity, attribute, value, signal, source, date, licence)`; website facts also keep a verbatim quote that is machine-checked against the source text.
**Why:** sources disagree (for example Metro codes 2,273 of 2,320 stops as "not possible" while other evidence conflicts), so we must keep every claim with its source instead of one merged value. It also lets us say "unknown" and "last confirmed in 2023", which is central to the research (RQ3 and RQ4).
**Alternatives:** one merged row per place (loses disagreement and provenance); free-text notes only (cannot be computed on).
**Costs / revisit if:** more rows and a merge step is needed to answer questions; the national plan extends the schema (v2) with confidence and evidence fields.
**Basis:** recorded (`study_design.md`, `data_design.md`, `progress_log.md`).

### D-02: Tool-using assistant, not plain RAG (2026-11-11, accepted)
**Decision:** structured questions go to query tools over DuckDB; open questions go to document retrieval; the model writes answers only from what the tools return, with sources.
**Why:** plain retrieval over text cannot do location filters or distance sorting, and an assistant that answers from memory could say "accessible" when it is not, which can strand someone (RQ4).
**Alternatives:** RAG over all text only; a fine-tuned model answering from memory.
**Costs / revisit if:** more engineering (tools, agent loop); needs an API key for the deployed model.
**Basis:** recorded (`assistant_design.md`).

### D-01: Regions are pinned to OSM boundary relations (2026-11-07, accepted)
**Decision:** each region is an OSM relation ID in `config/regions.yaml`, never matched by name.
**Why:** name matching picked the wrong place in the predecessor project ("Manhattan" matched Manhattan, Kansas).
**Alternatives:** name or geocoder lookup each time.
**Costs / revisit if:** adding a region needs one resolved ID; the national plan automates this step.
**Basis:** recorded (`config/regions.yaml` comment).
