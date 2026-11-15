# Plan: automated, nationwide data collection for the Accessibility Assistant

Status: **draft for review, nothing implemented yet.** Written 2026-11-15.

Companion docs: diagrams in [`architecture.md`](architecture.md); source kinds beyond government in [`source_types.md`](source_types.md); reasoning in [`decisions.md`](decisions.md).

## 0. Goal and constraints

> **Constraint: no budget for now ($0).** Everything below must run on free data, free tools and hardware we already have (a laptop, possibly lab or university machines). Section 0.1 says what that changes. Free-tier limits change often and were not all verified: re-check each before relying on it.

**Goal.** A multimodal data-fusion layer for a wheelchair accessibility assistant that works for any US place. This repo's maps are a visualization of that data, not the product. The product is the dataset plus the assistant that reasons over it.

### 0.1 What a $0 budget changes

| Plan element | Paid version (avoided) | Free replacement | Consequence |
|---|---|---|---|
| Finding sites (route D) | search API (Google, Bing, SerpAPI) | place-driven discovery from OSM `website` tags and Overture websites, sitemaps, open-data catalog APIs, Wayback and Common Crawl URL indexes; a handful of manual queries per region | slower and less complete for obscure sites; route D shrinks to a small hand-run supplement |
| Reading text (claim extraction, triage) | hosted LLM API | **rules first** (keyword and section matching, as the NYC predecessor did), then a **local open model** (for example through Ollama) on only the pages that pass; run overnight; cache by content hash | lower accuracy than a frontier model, so the quote-must-appear check and human review matter more |
| Reading images, posters, scans | hosted vision model | free OCR (Tesseract or PaddleOCR) first; a **local vision-language model** only on images that look relevant | slow; needs a GPU or patience; hand-check more |
| PDFs | paid document-AI services | free parsers (PyMuPDF, pdfplumber, Docling or Marker) | good for text PDFs; scanned and complex layouts need OCR |
| Triage of candidate sources | LLM reads metadata | keyword rules plus a small local embedding model for relevance; LLM draft only for the mapping step, locally | review queue is slightly longer |
| JavaScript pages | paid scraping services | Playwright headless browser (free) | slower crawl, more local compute |
| Storage and sharing | cloud buckets | local disk for raw files; free hosts for releases: Zenodo (DOI), Hugging Face Datasets, GitHub releases (with size limits), university storage | other team gets versioned files, not a live service |
| Serving to the other team | hosted API | files only (GeoParquet, DuckDB file); a read-only API only if someone can host it for free | fine for v1 |
| Assistant model | paid API key (Claude Pro does not include API use) | a local open model, or free-tier credits where available (check terms) | assistant quality is bounded by the local model; keep the tools-only evaluation, which needs no model |
| Compute | cloud GPUs | laptop, lab machines, free Colab tiers, or university compute if available (to ask) | prefer small regions and batch jobs |
| Ratings backend | paid database | Supabase free tier (already in use) | keep within its limits |

Principles that follow: (1) **spend compute only where it pays**: cheap rules and filters first, models last, and cache everything by content hash so nothing is processed twice; (2) **prefer structured and national sources**, which cost nothing to process; (3) **start with the two target regions and measure** time per page before scaling; (4) **record skipped work** (for example "needs vision model, not yet run") so the coverage report is honest; (5) ask early about free university or lab resources (GPU access, storage, research credits), and about free research access programs, which may remove some limits.

**What exists today** (Cincinnati and Oxford, built by hand): a declarative source registry (`config/sources.yaml`), regions pinned to OSM boundaries (`config/regions.yaml`), connectors for ArcGIS, Socrata, GTFS, Overpass, Overture, iCal and generic web pages, a common observation schema (entity, attribute, value, signal, source, date, license) and a DuckDB knowledge base for the assistant.

**What is new in the ask:**
1. Cover Maryland, DC, Dayton and more cities your professor will name, then the whole country.
2. **No hand-picked websites.** Sources must be discovered automatically.
3. Use more than text: PDFs, posters, maps, images.
4. Another lab team consumes the data in their own app, so the storage format, schema and documentation must be stable.
5. Cover every question a wheelchair user might ask, not just routing.
6. Keep a machine-readable description of what data we hold, so we can compute coverage and scores from it.

**Reference.** The MU-Smart/Accessibility-Assistant repo (NYC, Manhattan) did this at small scale: NYC neighborhood list, then Google search results per neighborhood, then page scraping to markdown, then keyword matching, then fuzzy matching to OSM places. Its weak points, which this plan fixes: manual, per-city scripts; search-engine dependence; keyword matching only; no provenance or licensing; no PDFs or images; fuzzy name matching with no geographic constraint.

## 1. Design principles

1. **One pipeline, parameterized by region.** Adding Maryland must not mean writing Maryland code. A new place is a config entry plus a command.
2. **Two kinds of sources, treated differently.**
   - *National layers* cover every region the day we add it: OSM, Overture, USGS 3DEP elevation, Census ACS, GTFS feeds (via the Mobility Database), NPS, FHWA/NTD data. Build these once.
   - *Local layers* (city sidewalk inventories, 311 data, ADA plans, venue pages) must be discovered per region.
3. **Discover, then triage, then approve.** Automated discovery proposes; an LLM classifier scores relevance from metadata; the trust engine rates it and accepts or rejects it automatically (see `system_overview.md` section 4) in a short review queue. Nothing unreviewed enters a release.
4. **Provenance on every fact.** Each observation keeps its source URL, retrieval time, a quote or page/bbox, the extraction method, a confidence score and the license.
5. **Raw data is immutable.** Store what we fetched, exactly as fetched, with a content hash. Re-extraction later (better model, new schema) never needs re-fetching.
6. **Legal and polite by default.** Respect robots.txt, rate limits and terms of service. Record licenses per source. Google Places and Yelp details are not stored for redistribution (as today).
7. **Description is data.** Every dataset gets a machine-readable card (what it contains, coverage, date, license) so we can calculate, for example, "this city has curb-ramp polygons but no slope data".

## 2. What a wheelchair user might ask: the scenario map

The attribute list itself lives in `data_landscape.md` section 1; the "Data needed" column below only names the families. This list drives everything: which attributes we need, which sources feed them, and later the evaluation question set. Each family needs an attribute list (extending the existing "target schema" in `docs/data_landscape.md`) and a coverage check per region.

| # | Question family | Examples | Data needed | Main source types |
|---|---|---|---|---|
| 1 | Route and path | Is there a step-free route from A to B? How steep? Is the sidewalk continuous? | sidewalks, curb ramps, slope, surface, width, crossings, steps | OSM, city GIS, 3DEP, sidewalk inventories |
| 2 | Crossings | Is there an audible signal? Enough crossing time? | signals, APS, refuge islands, curb cuts | city GIS, OSM, 311 |
| 3 | Entering a place | Step-free entrance? Door width? Automatic door? | entrance data, venue accessibility text | OSM, venue websites, PDFs |
| 4 | Inside a place | Accessible restroom? Elevator? Seating? Counter height? | restroom, elevator, layout | venue sites, floor-plan PDFs, images |
| 5 | Parking and drop-off | Accessible spaces? Van-accessible? Distance to entrance? | parking stalls, access aisles, drop-off points | OSM, city parking data, venue sites |
| 6 | Transit | Is the stop accessible? Is the elevator working today? Paratransit? | GTFS wheelchair fields, alerts, paratransit areas | GTFS, GTFS-RT, agency PDFs |
| 7 | Today's conditions | Construction, closures, snow, broken elevators | temporary closures, alerts | 311, permits, GTFS-RT, DOT feeds |
| 8 | Events and programs | Is this event accessible? Adaptive sports? | events, access notes, registration rules | iCal, tourism sites, posters |
| 9 | Services and health | Accessible clinics, repair for equipment, personal assistance | service providers, eligibility | agency sites, hospital sites, 211 |
| 10 | Rights and reporting | Who do I report a broken ramp to? What does the ADA require here? | contacts, complaint processes, transition plans | city/state ADA pages, DOJ |
| 11 | Housing and daily needs | Accessible housing, grocery, pharmacy | listings, POIs | HUD, OSM, Overture |
| 12 | Outdoors and recreation | Accessible trails, beaches, parks, adaptive equipment | trail surface/length/grade, facilities | NPS, state/county parks, PDFs |
| 13 | Lived experience | Is it actually usable? What do people say? | reviews, forum posts, user ratings | Reddit, our own ratings (Supabase), reviews with permission |
| 14 | Personal fit | "I use a power chair 28 in wide, max grade 6%" | user profile applied to the above | computed by the assistant |

The same families become the **evaluation set**: write 10 to 20 realistic questions per family and check whether the data can answer each one in each region.

## 3. Architecture

```
 Region registry ──► Source discovery ──► Trust engine (auto-approve) ──► Fetch (raw store)
                                                                          │
                       Extraction (text / PDF / image / table) ◄──────────┘
                                          │
                       Normalize to observations + entities (geocode, match to places)
                                          │
                       Fusion (dedupe, conflicts, confidence, freshness)
                                          │
                  Release (versioned files + dataset cards + DuckDB KB) ──► assistant, lab team's app, maps
```

### 3.1 Region registry (automatic)

- Input: a name like "Maryland", "Washington DC", "Dayton OH".
- Resolve through the Census TIGER boundary files and OSM (Nominatim), then **pin the OSM relation ID** (the existing rule, to avoid the "Manhattan, Kansas" mistake).
- A region has a level: `state`, `county`, `place`. A state expands to counties and its larger cities. Store FIPS/GEOID so Census data joins cleanly.
- Output: an entry in `config/regions.yaml`, generated and checked by the automatic rules in `system_overview.md` section 4.

### 3.2 Source discovery (the part you asked to automate)

Four automated routes, from most structured to least.

**A. Open-data catalogs (structured data).** Query catalog APIs with a keyword set (sidewalk, curb ramp, ADA, crosswalk, pedestrian signal, accessibility, bus stop, parking, 311, trail) restricted to the region's bounding box or jurisdiction:
- Data.gov CKAN catalog.
- Socrata Discovery API (covers many city and state portals).
- ArcGIS Hub / ArcGIS Online search, and ArcGIS REST service directories (the dominant platform for city GIS; CAGIS is one).
- State GIS clearinghouses and portals (found through the catalogs above).
- Mobility Database / Transitland for GTFS feeds.
- Census, CDC, HUD, FHWA, NPS APIs as national layers.
Each hit is a *candidate dataset* with metadata (title, description, fields, geometry type, update date, license).

**B. Government website discovery (documents and pages).** Build seed lists automatically:
- The official list of `.gov` domains (CISA dotgov dataset) filtered to the region's jurisdictions, plus transit agencies, DOTs, counties, cities, public universities, hospitals, park agencies.
- Crawl from the seeds within the same domain (sitemap first), scoring each page and link for accessibility relevance, and stopping at a depth and page budget.
- Targets: ADA coordinator pages, ADA transition plans, accessibility maps, paratransit pages, complaint forms.

**C. Place-driven discovery (venues and businesses).** This is the scalable core for the consumer questions:
- Start from the **place list** (OSM and Overture POIs in the region).
- Use the `website` tag where present; otherwise look it up in Overture, Wikidata or the venue's listing on a tourism site. A search API is optional (see 0.1); with no budget we use it only by hand.
- For each site, fetch only the pages that look like accessibility, visit, directions, parking or events pages (link text and URL patterns, then a classifier).
- Tourism boards ("Enjoy Oxford"-style visitor sites) are found the same way: search for the destination marketing organization per region, then crawl.

**D. Templated web search for what the above miss.** A fixed set of query templates per scenario family and region (for example "{city} ADA transition plan", "{city} accessible trails wheelchair", "{city} paratransit eligibility"). If we later have budget, use a proper search API (Brave, Bing, SerpAPI or Google Custom Search), never scraped results pages. With $0, run this route by hand for a short list of queries per region. Deduplicate by domain and keep only results that pass the relevance classifier.

Every route writes to one table, `source_candidates`: URL, discovery route, region, type guess, relevance score, license/robots status, status (`new`, `approved`, `rejected`, `ingested`).

### 3.3 Triage and review

- At $0 this uses keyword rules and a small local model (see 0.1). A cheap LLM pass reads **metadata and a short sample only** (not the whole source) and answers: what attribute family does this serve, what geometry, what fields map to which attributes, is it current, is the license usable.
- For structured candidates, the LLM drafts the `sources.yaml` entry (connector type, URL, `where` filter, field-to-attribute mapping). Automated checks then validate the draft: rows fall inside the region, geometry type matches, value distributions look sane, row count is plausible.
- **No human review.** The trust engine scores each candidate (authority, provenance, freshness, completeness, internal quality, cross-source agreement, track record) and routes it: Tier A accepted, Tier B accepted as "reported" only, Tier C quarantined, Tier D rejected. Rejected sources are remembered so they are not re-proposed.
- Over time, approved mappings become examples that improve the drafting.

### 3.4 Fetching and the raw store

- One generic fetcher per access pattern: file download, ArcGIS/Socrata/CKAN API paging, GTFS zip, HTML fetch, PDF/image download. Reuse the existing connectors.
- Respect robots.txt, rate limit per host, send an honest user agent, use ETag/If-Modified-Since to avoid re-downloads.
- Store `raw/{region}/{source_id}/{YYYY-MM-DD}/...` with a sidecar `manifest.json`: URL, fetched_at, HTTP status and headers, SHA-256, size, license, robots decision.
- Refresh schedule per source type: live alerts (minutes to hours), 311 and events (daily to weekly), inventories (monthly), plans and PDFs (quarterly), boundaries and elevation (yearly).

#### Completeness: making sure we fetch everything we might need

A crawl is only useful if we know what it missed. Rules, with diagrams 9 and 10 in [`architecture.md`](architecture.md):

1. **Every URL gets a final status.** The frontier records each URL as fetched, failed, skipped (with reason: robots.txt, off-site, over budget) or duplicate. "Unknown" is not allowed at the end of a crawl. (The repo already counts failed fetches and robots-skipped pages in `source_inventory.md`; this extends it.)
2. **Several ways to find pages, not just following links:** the seed page, `sitemap.xml` and sitemaps listed in `robots.txt`, RSS and calendar feeds, and the URL lists of the Wayback Machine and Common Crawl for the same domain.
3. **Fetch what a plain download misses:** pages that need JavaScript, content hidden in tabs and accordions, "load more" and numbered pagination, iframes and embedded viewers, and linked PDFs, images and spreadsheets (registered as documents, then extracted).
4. **Structured sources are paged until exhausted,** and the total the server reports (ArcGIS `returnCountOnly`, Socrata count, API totals) is compared with the rows saved.
5. **Six completeness gates** after each crawl: status audit, sitemap coverage, count check, archive check, keyword audit (a site's own search for wheelchair, accessible, ADA, ramp, elevator versus pages we fetched), and a random sample of uncrawled pages checked for relevance.
6. **Gaps are queued, not ignored:** retry, re-fetch with a headless browser, raise depth or budget, ask the owner, or mark blocked with the reason. A source is "complete" only when the gates pass; otherwise the coverage report shows exactly what is missing.
7. **Budgets are explicit.** If a crawl stops because of a page or time budget, that is reported as incomplete rather than finished.
8. **Re-crawls compare with the last crawl,** so removed pages and changed content are noticed (see refresh schedule above).

Limits to state honestly: some pages are behind logins, robots.txt exclusions or paywalls, and "everything we might need" can only be measured against the independent checks above, not against an unknown total.

### 3.5 Multimodal extraction

| Input | Method | Output |
|---|---|---|
| HTML page | main-content extraction to markdown, split by headings | text chunks with heading path |
| Text PDF | text and table extraction with layout (page, bbox kept) | text chunks, tables |
| Scanned PDF, poster, flyer | OCR plus a vision-language model for layout and meaning | text, plus a structured summary |
| Map, floor plan, trail map, signage photo | vision-language model describes accessibility-relevant features; geo-referenced only when the source gives coordinates | description, labeled features, confidence |
| Tables (for example a plan's barrier inventory) | table parser, then row-wise normalization | rows as observations |
| Video / audio | out of scope for v1; revisit later | |

Then **claim extraction**: an LLM turns each chunk into typed claims against our attribute taxonomy, with the supporting quote (and page/bbox). Claims are rejected if the quote does not actually appear in the source. Images and PDFs are kept next to the claims so a human or the assistant can look at the original.

### 3.6 Entities and matching

- Backbone of **entities** (places, path segments, curb ramps, transit stops, events) from OSM and Overture, each with a stable ID.
- Match extracted claims to entities by name **and** location (and address when present), not by fuzzy name alone. Low-confidence matches go to a review list rather than being merged.
- Keep source records linked to the entity so one place can show OSM, city data and web text side by side.

### 3.7 Fusion

- Combine per entity and attribute: keep all observations, compute a resolved value with confidence, and flag conflicts (for example OSM says `wheelchair=yes`, a venue page says "no step-free entrance").
- Weight by source type (official inventory > venue statement > crowd data > inferred), recency and extraction confidence.
- Staleness: each observation has an age; the assistant can say "last confirmed in 2023".
- Derived metrics computed here, with formulas documented: segment accessibility score (slope, surface, width, kerbs), coverage per region and attribute, ramp density, and so on.

## 4. Storage and formats (for the other lab team)

Aim: files they can read without our code, with a documented contract.

- **Tabular and geographic data:** GeoParquet (compact, typed, readable from Python, R, DuckDB, QGIS). GeoJSON export on request for small layers.
- **Layout:** `release/v{N}/{region}/{table}.parquet`, with tables `entities`, `observations`, `documents`, `sources`, `datasets` (cards), `matches`.
- **Documents and media:** originals in an object store (a bucket or the lab server), referenced by hash and URL from `documents`; extracted text next to them.
- **Dataset cards** (`datasets` table plus one JSON per dataset, in a DCAT-style shape): id, title, publisher, URL, license, update frequency, geometry type, row count, fields, which attributes it feeds, coverage (share of the region covered), freshness, known issues. These are what we use to calculate things.
- **Observation schema (v2, extends the current one):** entity_id, attribute, value, signal (supports/barrier/neutral), source_id, source_url, retrieved_at, observed_at (when known), valid_from/valid_to, evidence (quote, page, bbox, image ref), extraction_method (structured / rule / LLM / VLM / manual), confidence, license, region, geometry.
- **Contract:** semantic versioning of the schema, a changelog, a data dictionary generated from code, and a `LICENSES` manifest saying which sources may be redistributed. Breaking changes only on a major version.
- **Serving to the other app:** v1 as versioned files in a shared bucket or repo release; a small read-only API (FastAPI over DuckDB) later if they need queries. Ask them which they prefer before building (open question below).
- **Assistant KB:** keep DuckDB (`atlas.duckdb`) built from the release, with embeddings for text chunks for retrieval.

## 5. Quality and evaluation

- **Source-level checks:** schema, bounding box, duplicates, date sanity, license present.
- **Extraction checks:** quote must exist in the source text; confidence threshold; sample 50 claims per source type and measure precision by hand.
- **Coverage report per region:** for each scenario family, which attributes exist and for what share of the region (generated from the dataset cards). This is the "what can the assistant answer here" page.
- **Question-set evaluation:** the scenario questions from section 2, answered with and without each source, to show what each source adds.
- **Comparison data:** Google Places stays comparison-only, as now.
- **No manual checking is assumed.** Quality is estimated by the automatic checks in `system_overview.md` section 4 (quote check, double extraction, entailment check, reference data, question bank, planted tests). If time allows, a one-time labelled set of about 100 facts, built automatically from official data, calibrates the weights.

## 6. Risks and how we handle them

| Risk | Handling |
|---|---|
| Terms of service and copyright of scraped sites | robots.txt, rate limits, store snippets and facts plus a link, not whole-site mirrors for redistribution; per-source license field; ask the professor/IRB about anything unclear |
| LLM errors and hallucinated claims | quote-must-appear rule, double extraction, entailment check, confidence tiers, precision estimated against reference data |
| Cost at national scale | LLMs read metadata and sampled pages first; heavy extraction only for approved sources; cache by content hash |
| Search API cost and quotas | per-region query budgets; prefer place-driven discovery (OSM `website`) over search |
| Stale or wrong data | freshness shown on every fact, re-fetch schedule, conflict flags |
| Personal data in forums | only public posts, strip usernames, follow Reddit API terms |
| Messy local data (a different schema per city) | LLM-drafted mapping plus automated validation, then automatic scoring and approval |
| Scope creep | fixed phases below; each phase has a demo and a numeric exit criterion |

## 7. Phases

**Phase 0: foundations (about 1 week).** Observation schema v2; raw-store manifest; `source_candidates` and `datasets` tables; dataset-card generator run on the existing Cincinnati and Oxford sources as proof; scenario list and question set drafted.

**Phase 1: region-in-a-box and structured sources (about 2 weeks).** Region resolver (Census + OSM). Catalog discovery (CKAN, Socrata, ArcGIS Hub, Mobility Database) and the triage and review UI. National layers for any region (OSM, Overture, 3DEP, ACS, GTFS). *Exit:* Washington DC and Maryland have a coverage report with reviewed sources; Cincinnati and Oxford reproduce through the new pipeline with no loss.

**Phase 2: web discovery (about 2 weeks).** Government-site crawl, place-driven site discovery, query-template search. HTML extraction and claim extraction. *Exit:* for DC, at least N venues (target set with the professor) have accessibility claims with quotes; precision on a 100-claim sample reported.

**Phase 3: multimodal (about 2 weeks).** PDF (text and scanned), image/poster/map handling with a vision-language model, table extraction (for example an ADA transition plan inventory). *Exit:* at least one transition plan and one set of venue posters or maps converted to observations with evidence images.

**Phase 4: fusion and the release for the other team (about 1 to 2 weeks).** Entity matching, conflict handling, scoring, first versioned release (GeoParquet + dictionary + licenses), agreement with the other team on the contract. *Exit:* they can load a region without our code.

**Phase 5: scale (ongoing).** Add Dayton and the other cities, then states in batches. Scheduling and monitoring (what failed, what changed). Keep the review queue small by auto-approving high-confidence mappings that match patterns already approved.

(Time estimates assume one person and are rough.)

## 8. First concrete steps after you approve

1. Write the schema v2 and the dataset-card format, and regenerate cards for the existing sources.
2. Build the region resolver and add `dc`, `maryland` (as counties), `dayton` through it.
3. Build the catalog discovery for ArcGIS Hub and Socrata first (DC is ArcGIS-Hub based; many Maryland counties publish through Socrata or ArcGIS), then CKAN and Mobility Database.
4. Run discovery for DC only and look at the candidate list together, to tune relevance scoring before scaling.

## 9. Open questions for you, your professor and the other team

1. **Which cities exactly,** and the deadline for Maryland and DC? Is "Maryland" the whole state or a few counties (for example Montgomery, Prince George's, Baltimore)?
2. **Free resources:** with no budget, can we use lab or university machines (GPU, storage) and research credits? Where can large files live for free (lab server, university storage, Zenodo, Hugging Face)?
3. **The other team:** which format do they want (Parquet, GeoJSON, SQLite/DuckDB, REST API), how often do they need updates, and which attributes matter most for their app?
4. **Licensing stance:** are we only releasing data with clearly open licenses, or also fact-level extractions from websites (with links back)?
5. **Reddit and reviews:** keep Reddit in scope, given the terms and need for keys?
6. **Rating cut-offs:** are the tier thresholds (80 / 50 / 30) and starting weights in `system_overview.md` acceptable?
7. **Scope of "multimodal":** are photos from street imagery (Mapillary) in scope, or only documents, posters and maps?
