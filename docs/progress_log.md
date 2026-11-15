# Progress log and findings

_Snapshot from the Claude Doc "Data & RAG Implementation Plan" (12 Nov 2026). The Claude Doc is where this is kept current; copy updates here when you commit._

## Progress and to-do

The maps are live: [Cincinnati](https://zenaism.github.io/accessibility-map/data/map/cincinnati.html) and [Oxford](https://zenaism.github.io/accessibility-map/data/map/oxford.html). Places without accessibility information: Oxford 9% of 176 places (was 84% of 31), Cincinnati 57% of 478 (was 77% of 354). 242 quoted facts, 5 posters read. Updated 12 November 2026.

### Done

| Date | What | Where |
| --- | --- | --- |
| 2026-11-13 | One-page notes on which research questions the system can answer and how: 5 of 8 inside the system (RQ2 today; RQ5 and RQ6 once a model is connected to the 6 tools; RQ3 and RQ4 start in the system and are finished by a field audit), 3 need people (RQ1, RQ7, RQ8). Includes a figure placing each question on the system pipeline. Current counts: 676 places, 972 facts (27 about vision, at 15 places), 229 events | docs/research\_questions\_system\_notes.docx, docs/figures/rq\_system\_map.png (not committed yet) |
| 2026-11-13 | Research brief for the assistant, written from the view of a person who has low vision or is blind and uses a wheelchair: who they are (44.9% of US adults with vision impairment also report a mobility disability), a day of questions, what the research says, 8 research questions each explained (why, what is known, method, measures, expected result, risks), a stronger version of the prompt, and 24 new questions for the question bank. 56 sources, 24 checked at the source. Suggested start: needs study (ethics application), answerability analysis, grounded-answer benchmark | docs/accessibility\_assistant\_research\_brief.docx (Word, not committed yet) |
| 2026-11-12 | Google area searches (25 requests, within the free allowance and the daily quota): 281 new places with Google accessibility answers (restaurants, cafés, bars, breweries, hotels, pharmacies, groceries) in the private map only. Private map: Cincinnati 710 places, Oxford 229. Public map unchanged | data/private/ (not published) |
| 2026-11-12 | Free address, phone, website and opening hours from OpenStreetMap and Overture (openly licensed, on the public map): Cincinnati 159 / 122 / 133 / 55, Oxford 137 / 92 / 111 / 7. Assistant search now uses addresses safely (name or all words must match). Next with Google, only after a hard daily quota is set: accessibility for new restaurants and cafés, within the free allowance | live maps |
| 2026-11-12 | Google Places key works. Private, local-only copy (data/private/, git-ignored, never published): 305 places looked up, 278 matched by distance and name, 219 with Google's wheelchair fields. In the private map, accessible places rise from 125 to 149 (Cincinnati) and 5 to 39 (Oxford). Public map unchanged; storing Google data goes against Google's terms, so it must stay private | scripts/google\_places\_private.py |
| 2026-11-12 | Routes for blind travelers: each crossing described (signal, audible, marked/unmarked, tactile paving), crossing summary per route, 'no sidewalk mapped here' warnings, and a 'Route with safer crossings' when it differs (Cincinnati 28, Oxford 42 places); assistant route tool has a blind option | src/atlas/routing.py |
| 2026-11-12 | Step-free routes: walking network from OSM (Cincinnati 4,245 km, Oxford 461 km) with USGS slopes; routes never use stairs and avoid steep sections, roads without sidewalks, rough surfaces and raised kerbs. Every place with a nearby bus stop gets directions in words to its accessible entrance (287 of 293), shown in Details with 'Show route on map' and on text pages; assistant tool accessible\_route | src/atlas/routing.py |
| 2026-11-12 | Assistant tool area\_conditions: how hilly an area is (Mt. Adams: 42% of path sections steeper than a ramp, 22 stairways), curb ramps, open 311 sidewalk reports. Question bank now 35/35 answerable, 9 gaps left (Findlay Market restroom, Uptown restroom hours, Oxford restaurant restrooms, Northside brewery ramps, Skyline on Ludlow, Oxford curb ramps, waterfall without stairs, Disability Pride date, support groups) | src/atlas/assistant/tools.py |
| 2026-11-12 | Question-bank gaps closed (15 → 11): Metro Access sign-up steps and contacts, all regional buses lift/ramp-equipped, one shared paratransit application, 311 for broken curb ramps, CRC inclusion and 22 accessible pools, and 3 mobility businesses confirmed on their own sites (accessible vans, rentals, lift repair) with a new map filter. Findlay Market, Washington Park, Fountain Square: no accessibility information on their sites | 261 facts |
| 2026-11-12 | Miami DST 272 student audit (OACB reprint of the WCPO story): Oxford Municipal Court ramp only at the rear and only on request; TRI Community Center flagged. Weekly automatic refresh postponed; you will set it up later (make refresh works by hand) | 245 facts |
| 2026-11-12 | Findings so far: 8 measured results (OSM coverage, campus sources disagreeing, wheelchair vs vision information, unknowns, transit feed problem, old and self-reported evidence, unanswerable questions, equity) plus questions for the professor | this doc, Findings section |
| 2026-11-12 | Assistant groundwork (no AI yet): DuckDB knowledge base (667 places incl. organizations, 953 facts, 229 events), 4 lookup tools with evidence, the question bank as eval/questions.yaml, and a tools-only evaluation: 29/29 answerable questions find the right place in the top 5, 15 are data gaps. Caveat: expected answers were written after seeing the data, so it is a regression baseline, not a quality score | src/atlas/assistant/, eval/ |
| 2026-11-12 | Tests 29 → 55: theatre schedule and restaurant parsers, rating rules, What is known line, summaries, directions wording, page dates, refresh age. Verified by breaking two rules on purpose (both caught) | tests/ |
| 2026-11-12 | make refresh: one command re-downloads calendars and theatre schedules, rebuilds, tests and publishes. Fixed: saved pages never expired (a refresh would have re-read old copies); facts now stay checkable against the archived page version they quote. Runs on the Mac (the data is too big and partly not redistributable for a GitHub job) | scripts/refresh.sh |
| 2026-11-12 | Oxford deep dive: Miami 2023 parking map read (69 buildings with accessible entrances; 63 agree with OSM, 33 OSM-tagged buildings have no arrow); 2026 Natural Areas trail map (3 paved trails); student press 2019 (Thomson Hall steps only, Boyd Hall rear entrances); Hall Auditorium and Millett Hall wheelchair entry; 43 Uptown restaurants listed wheelchair accessible by Enjoy Oxford. Oxford now 176 places, 9% without information | data/manual/posters/, live maps |
| 2026-11-12 | All 40 saved images reviewed (contact sheet): almost all photos. New poster read: Cincinnati Zoo Welcome Center map 2026 (wheelchair rental, family and sensory-friendly restrooms). Poster facts can now be added to places already on the map | data/manual/posters/ |
| 2026-11-12 | Pass over saved Cincinnati pages: Cincinnati Nature Center accessible trail and ADA parking; Great Parks accessible playgrounds and canoe launches placed on Winton Woods, Sharon Woods, Francis RecreAcres; Winton Woods Farm events now placed. 232 facts in total | live maps |
| 2026-11-12 | Pass over saved Oxford pages (78 docs): Miami Art Museum (street-level entries, but closed until fall 2027), Ruder Preserve ADA boardwalks, Governor Bebb trail warning, MetroParks service animals. New "Notice" facts show closures first and never count as access | 224 facts |
| 2026-11-12 | Disability-focused events: adapted sports feed (Mayerson JCC), Butler County DD sensory-friendly screening; duplicate feed events merged; new "Adaptive sports & disability events" filter. Hamilton County DDS and the Autism Society block automated reading; CILO and Disability Pride sites did not respond | live maps |
| 2026-11-12 | More venues (24 facts, 216 total): Taft Theatre (no elevator, balcony stairs only), Ensemble Theatre, Music Hall restrooms and elevators (now rated accessible), Downtown Main Library (braille, described videos), Hall Auditorium and Millett Hall accessible parking, Armstrong Student Center. Krohn, Smale and Lane Libraries pages had no accessibility text | data/extracted/venue\_facts.jsonl |
| 2026-11-12 | Accessible performances by date: 31 audio-described, ASL and sensory-friendly shows (26 upcoming) from the Playhouse, Children's Theatre and Cincinnati Shakespeare; new map filter and a by-month text page. Broadway in Cincinnati blocks automated reading; the Art Museum lists touch tours without dates | places/cincinnati/shows.html |
| 2026-11-12 | README rewritten short: what it is, maps and text-page links, one source table with current counts, four findings, how to run | README.md |
| 2026-11-12 | Text-only page for every place (595 pages) and an A–Z index per city: what is known, arriving, getting there, every fact with quote and source, events, contacts. Linked from Details and the map header | data/map/places/ |
| 2026-11-12 | Cards say what is known first: a short "What is known" list (Entrance, Restroom, Inside, Elevator, Braille, Audio description… with yes / partly / no / not known) right after the rating; long text moved into Details | live maps |
| 2026-11-12 | Arrival description in words (130 places in Cincinnati, 104 in Oxford): which side the accessible entrance is on, street and door type, warning when the main entrance is not accessible, the venue's own entrance text, and distance and direction from the nearest bus stop to that entrance. Marked as computed, not checked on site | live maps |
| 2026-11-12 | Paging for the place list: 20 per page, numbered pages with previous and next, page announced to screen readers, focus moves to the first place; fits on one line on desktop, tablet and phone | live maps |
| 2026-11-12 | Blind or low vision filter: braille, large print, audio description and touch facts from 12 venues (22 new facts, 192 total), plus crossings with accessible signals and tactile paving near each place. Filters and search now also apply to the map, not just the list | live maps |
| 2026-11-12 | Getting there, in every place's details: nearest bus stop and distance, path sections steeper than a ramp (8.33%) within 500 ft, mapped stairways, city curb ramps, and sidewalk or curb 311 reports in the past year (Cincinnati) | live maps |
| 2026-11-12 | Fixed: opening Details made the page grow and showed an empty area below the map; the page now stays screen height and only the list scrolls | live maps |
| 2026-11-12 | Filled in the map: 97 Miami campus buildings from OSM entrance tags, 31 food and drink places, 37 shops and services, 10 venues from their own current pages (Zoo, Freedom Center, Contemporary Arts Center, Aronoff, Music Hall, ballpark, Reds Hall of Fame, Playhouse, Cincinnati Shakespeare, Children's Theatre); 170 quote-checked facts | `osm_entrances` connector, `data/extracted/venue_facts.jsonl` |
| 2026-11-12 | Map quick fixes: events inside their place cards, When filter for events, "source may be out of date" warning, Copy link, Report a problem, better default order | `src/atlas/map_viewer.py` |
| 2026-11-12 | Minimal redesign: collapsible list (edge tab), phone bottom sheet, tablet layout; list-first for screen readers; axe reports no violations | live maps |
| 2026-11-11 | Search box and Near me (distance and direction in words) | live maps |
| 2026-11-11 | Maps published on GitHub Pages; USGS basemap (public domain); GitHub-styled GeoJSON previews | `data/map/` |
| 2026-11-11 | First map: GeoJSON per city, viewer with icons and legend, review list of anything not placed | `make map` |
| 2026-11-11 | TrailLink trails (47), Cincinnati Parks calendar feed (264 events, 53 tagged Accessible), 408 Miami events sorted, page events | `data/extracted/` |
| 2026-11-11 | Trail posters read with zoom checks: Oxford trail system, Hueston Woods map, Edge of Appalachia | `data/manual/posters/` |
| 2026-11-11 | Website, PDF and calendar connectors with raw files kept; Overture places; OSM destinations; per-source inventory | `docs/source_inventory.md` |
| 2026-11-11 | Git history cleaned: all commits under zenaism@miamioh.edu, no Copilot credit line | GitHub |

### To do: next (I can do these)

- [ ] Scrape new sources: The Bridge Adaptive Sports (thebridgeadaptive.org), University of Cincinnati (uc.edu), UC Health (uchealth.com), Cincinnati Children's Hospital (cincinnatichildrens.org), Flying Pig Marathon community events (flyingpigmarathon.com/community-events), and Grandma's Marathon (grandmasmarathon.com; note: held in Duluth, MN, outside our area; check whether the Flying Pig Marathon was meant)
- [ ] Parking accessibility on the Miami campus: where accessible spaces are in each lot, how many, permit rules, drop-off points near main buildings (sources: Parking & Transportation pages and maps, 2023 parking map, email to parking@MiamiOH.edu)
- [ ] Paging for the place list instead of "Show more" (done)
- [ ] Arrival description in words for every place: from the nearest bus stop to the accessible entrance (which side, door type, crossings with accessible signals), marked as computed until checked on site (done; about 1–2 hours)
- [ ] Audio-described performances and touch tours by date (Playhouse, Aronoff, Children's Theatre, Art Museum), as a "this month" view (done; Broadway in Cincinnati still missing: it blocks automated reading)
- [ ] A simple page for each place (headings, no map, loads fast, easy to share, good for screen readers and the assistant) (done)
- [ ] Card order for screen readers: what is known for a visit first, then the rating text (done)
- [ ] Getting there and step-by-step step-free routes (done; next: check a sample of routes on site)
- [ ] Blind and low vision filter (done for Cincinnati; Oxford has no vision facts yet: ask Miami Student Disability Services and the library)
- [ ] More venues from their own pages (mostly done; still missing: Krohn, Smale, Lane Libraries, Kings Island, Newport Aquarium; these pages have no accessibility text or block automated reading): Krohn, Smale and riverfront parks, Kings Island, Newport Aquarium (both blocked automated reads), libraries, Taft Theatre
- [ ] Restaurants and cafes beyond OSM tags (Uptown Oxford, downtown Cincinnati)
- [ ] Events: more disability-focused calendars (done for sites with feeds or readable pages; Hamilton County DDS, Autism Society, CILO, Disability Pride need someone to save the pages or ask for a feed)
- [ ] Assistant v0: DuckDB plus tools plus a first run on the question bank (tools and tools-only run done; agent loop needs the Claude key), answering spoken-style questions with sources (after the items above)
- [ ] README rewrite to the short version planned below (done)

### To do: needs you

- [ ] Spot-check 20 venue facts and the 3 poster records (all marked not yet checked by a person)
- [ ] Verify zenaism@miamioh.edu on your GitHub account so commits link to you (done: commits already link to zenaism)
- [ ] Claude API key for the assistant
- [ ] Google Places and Yelp access; Meta Content Library application; Reddit API credentials
- [ ] Emails: City of Oxford (ADA transition plan), Miami Parking & Transportation (accessible-entrance map), Wheel the World and AccessNow (data partnership), All In Events (Blink maps)
- [ ] Download by hand (the sites block automated reading): Oxford's 2021 ADA Transition Plan PDF (cms9files.revize.com, robots.txt), Broadway in Cincinnati accessible performances, Hamilton County DDS and Autism Society event calendars, Kings Island and Newport Aquarium access pages. Save them into data/manual/ and I will read them
- [ ] Ask Prof. Kathy McMahon-Klosterman (or the Miami Student) for the student-made Uptown Access Guide; ask Miami Parking Services whether the 2026 map will show accessible entrances again
- [ ] Spot-check the 2023 parking-map reading (69 buildings, tiles in data/manual/posters/miami\_parking\_map\_2023/crops)

### To do: research

- [ ] Test the map with one or two wheelchair users, ideally one also blind (CILO or Student Disability Services)
- [ ] Decide how much weight old sources get in ratings
- [ ] Read the research brief and choose which of its 8 research questions to keep; discuss with the professor
- [ ] File the ethics (IRB) application for interviews with people who have both a vision and a mobility disability (brief, RQ1)
- [ ] Add the 24 vision and combined-profile questions from the brief's Appendix B to eval/questions.yaml

## Findings so far (for discussion)

Early results from the data collected on 11–12 November 2026. Each one is something we can measure again later; none is a final claim.

1. **Open maps say almost nothing about access.** Only 1.6% of named places in OpenStreetMap carry any wheelchair tag: 99 of 6,235 in Cincinnati and 8 of 464 in Oxford. Most of what the map knows comes from reading venues' own pages, not from open map data.
2. **Official campus sources disagree with each other and with OSM.** Miami's 2023 parking map marks accessible entrances on 69 buildings; 63 of those also have an accessible entrance in OSM. But 33 buildings that OSM tags as having one carry no arrow on the 2023 map, and the fall 2026 map dropped the symbols entirely. A 2019 student-newspaper report says Thomson Hall had only stepped entrances; OSM now shows an accessible entrance at Dodds Hall, which the same article listed as having none, so renovations likely explain part of the gap.
3. **Venues describe wheelchair access far more than blind or low-vision access.** Of 59 venues with quoted facts, 39 state something about wheelchair access and 15 about braille, large print, audio description or touch. Ten mention audio description, but only three theatres publish the dates of described performances (31 shows found).
4. **The remaining unknowns are mostly restrooms.** In Cincinnati, 259 of the 273 places without information are public restrooms whose OSM entry has no wheelchair tag. Oxford's unknowns fell from 84% to 9% once campus entrance data and the 2023 map were added.
5. **Transit data is unreliable for wheelchair users.** Cincinnati Metro's schedule feed codes 2,273 of 2,320 stops as "wheelchair boarding not possible" and 47 as possible. That conflicts with an accessible bus fleet and is likely a feed coding problem, so the map does not use it as evidence. Butler County's feed (2019) gives no accessibility at all.
6. **Much evidence is old or self-reported.** 53 of 242 quoted facts are more than three years old (the oldest from a 2016 visitor guide). 43 of 59 Oxford restaurants in the Enjoy Oxford directory are tagged "wheelchair accessible" by the business itself, with no detail on entrance or restroom. Both need a visible warning, which the map now gives.
7. **A third of realistic questions cannot be answered from public data yet.** Of the 44 questions in the bank, 15 need data we do not have: restroom hours, curb ramps in Oxford, sidewalk closures, paratransit sign-up, wheelchair repair, breweries with ramps, Findlay Market's restroom. These gaps are where outreach and partnerships matter most.
8. **Neighbourhood equity (Cincinnati, from the earlier analysis).** Census areas with $10,000 higher median income file about 10% more hazardous-sidewalk reports per resident (95% CI 5–15%); reporting reflects who reports, not only where problems are.

9) **The shortest way is often not wheelchair-usable on campus.** In 150 random trips between Miami buildings, the shortest walking route had stairs or a section steeper than a ramp in 39% of cases; the step-free alternative was a median 161 feet longer. Routes come from OpenStreetMap paths and elevation estimates and need checking on site.

10. **Safer crossings cost almost nothing, but audible signals are invisible in the data.** Preferring signalised crossings changed 64% of 131 Oxford routes and cut unmarked or unmapped crossings from 183 to 88, for a median of 11 extra feet. But only 12 of 3,552 signalised crossing segments in Cincinnati (and 4 in Oxford) are tagged as audible in OpenStreetMap, and the city's own signal inventory has no field for accessible pedestrian signals. Which signals talk is unknown: a question for the City of Cincinnati.

**Questions for the professor:** Should finding 2 become a small study (walk-check a sample of the 33 disputed buildings)? Do we need IRB review before testing the map with blind and wheelchair users? How should old and self-reported evidence count in the ratings?


## Original phase plan for Cincinnati and Oxford (11 Nov 2026, for the record)


**README (done).** The current README is about 200 lines. The new one will have four parts: a one-paragraph purpose, the data table below, how to run it (5 commands), and a link to this plan and `SOURCES.md`. The figures, findings and long explanations move to `docs/`.

| Source | What the data is about | Region | Time span | Records |
| --- | --- | --- | --- | --- |
| OpenStreetMap | places, paths, kerbs, crossings with access tags | both | edits 2008–2026 | filled at build |
| Cincinnati 311 | sidewalk, curb, ramp, signal complaints | Cincinnati | 2004–2026 | 24,639 |
| …one row per source… |  |  |  |  |

The table is generated from `config/sources.yaml` and the built files by `make readme`, so the counts and dates never drift.

**New repo layout**

```
config/attributes.yaml        controlled vocabulary
config/sources.yaml           + new sources (crawl, ical, poster, ...)
src/atlas/connectors/         + ical.py, wp_events.py, html_crawl.py, pdf.py, poster.py, overture.py, google_places.py, yelp.py
src/atlas/extract/            LLM extraction schemas and prompts
src/atlas/resolve.py          entity matching and access_summary
src/atlas/export_map.py       GeoJSON + CSV + Leaflet viewer
src/atlas/assistant/          tools, agent loop, document index
eval/questions.yaml           question bank with expected answers
data/manual/                  hand-checked CSVs (poster trails, venue reviews)
data/map/                     GeoJSON outputs (committed, small)
```

**Phases**

1. **Phase 1, places and venues (2 weeks).** Overture places, OSM restroom and access tags, museum and venue access pages, government pages. Output: the first GeoJSON map and the new README.
2. **Phase 2, trails (1–2 weeks).** OSM trails, Oxford Area Trails, Tri-State Trails, Great Parks, poster extraction with a hand check.
3. **Phase 3, events (1 week).** iCal, WordPress and HTML calendar connectors, the weekly refresh, the event layer.
4. **Phase 4, assistant v0 (2 weeks).** DuckDB and vector index, the tools, the agent loop, a command-line chat, and a first evaluation run on the question bank.
5. **Phase 5, community and paid sources (after approvals).** Reddit, Meta Content Library, Google and Yelp checks.

**Decisions for you to make before I start**

- [x] Google Places and Yelp: kept in the source list; you are checking free access.
- [x] Facebook: Meta Content Library kept in the list; you are checking access.
- [x] Map: GeoJSON only for now.
- [ ] Models: a Claude API key for the deployed assistant (Pro does not include API use).
- [ ] Area: confirm full city limits plus 25 km (Cincinnati) and 15 km (Oxford).


### Collection status (as of 11 November 2026)

Raw files are saved exactly as received in `data/raw/` (web pages under `data/raw/web/<source>/` with a `manifest.jsonl` download log and browser screenshots). Cleaned data goes to `data/processed/<region>/`: `.entities` and `.obs` for places and facts, `.docs` for page text, `.events` for events. Hand-checked extractions go to `data/manual/`.

| Source | Collected | What we have | Next step |
| --- | --- | --- | --- |
| Street layers: OSM streets, CAGIS ramps/sidewalks/steps/signals, 311, Metro and BCRTA buses, USGS slope | Yes | collected before this plan | none |
| Overture places (release 2026-10-21.0) | Yes | 92,859 places around Cincinnati, 2,758 around Oxford | match to access facts |
| OSM destinations: trails, parks, restrooms, culture, recreation | Yes | Cincinnati 5,054 features (1,525 trails, 310 restrooms); Oxford 285 (109 trails, 14 restrooms) | trail ratings |
| Cincinnati museums and venues: Museum Center, Art Museum, Taft, Taft NHS, Visit Cincy, Blink | Yes | 25 documents incl. 17 PDFs; read into facts | you spot-check facts |
| Oxford venues and services: Museums at Miami (Cocks, Hefner, Limper, McGuffey), Miami Student Disability Services, Hueston Woods Lodge, City of Oxford parks, Enjoy Oxford (incl. welcome guides, walking tours), Travel Butler County (all Oxford listings) | Yes | 79 documents incl. 12 PDFs; read into facts | you spot-check facts |
| MetroParks of Butler County (accessibility, GRIT all-terrain chairs, mobility-device policy) | Yes | 4 pages and PDFs; read into facts | none |
| Great Parks of Hamilton County (accessibility, trails, playgrounds) | Yes | 3 pages + resource plan PDF; read into facts | confirm Sharon Woods trail status |
| Five Rivers MetroParks paved trails (Dayton, outside both areas) | Yes | trail list page + photos; flagged as day trip | none |
| Trail posters: Oxford Area Trails system map, Hueston Woods park map, 5 Edge of Appalachia maps | Yes | read into `data/manual/posters/` with source files and zoom crops | you check each poster record |
| Event feeds (iCal): Cincy Jewfolk accessible events, Global Cincinnati, Miami University | Yes | 30 Cincinnati events; 264 Cincinnati Parks events (53 tagged Accessible by Parks); 408 upcoming Miami events sorted: 181 public, 215 campus-only, 7 staff training, 5 break notices | you check the sorting rules |
| Venue facts with verbatim quotes | Yes | 133 facts on 34 places, all quotes machine-checked, in `data/extracted/venue_facts.jsonl` | you spot-check |
| Programs and calendars without feeds: CRC therapeutic rec, UC Adaptive Athletics, The Bridge, Cincinnati Children's, Cincinnati Parks and Great Parks calendars | Yes | 8 dated events (3 adaptive sport from The Bridge, 5 Great Parks); facts from The Bridge, UC Adaptive Athletics and Cincinnati Parks articles | CRC program pages moved: find new URLs |
| Wheel the World | Yes | public homepage only (other listings need a partnership) | ask for data partnership |
| TrailLink city pages | Yes | 47 trails (40 in Ohio, 44 fully paved) in data/extracted/traillink\_trails.jsonl; parse checked against every page | match trails to OSM geometry |
| City of Oxford ADA transition plan | Partly | page exists but is empty on the live site | request the plan from the city |
| Miami campus accessible-entrance map | Partly | SDS says it is on the Parking & Transportation site | find and read the map |
| BLINK 2026 accessibility maps and FAQ | Blocked | removed after the festival (404); no Internet Archive copy | ask All In Events, or capture before Blink 2027 |
| Tri-State Trails | Blocked | site refuses automated requests (403) | ask for data or check by hand |
| OOD (ood.ohio.gov) | Blocked | site answers 404 to automated requests | check by hand |
| Universal Changing Table Map | Blocked | domain did not resolve | find current address |
| Cincinnati Pride accessibility page | Blocked | page moved (404) | find new URL |
| Google Places, Yelp | Not yet | not started | you are checking access |
| Meta Content Library (Facebook) | Not yet | not started | you are checking access |
| Reddit | Not yet | connector exists, not run | needs Reddit API credentials |
| Wheelmap / accessibility.cloud, AccessNow, Project Sidewalk | Not yet | not started | request keys or partnership |
| More events: libraries, theaters, Visit Cincy, Eventbrite, Meetup, ADA network | Not yet | not started | next batch |
| ADA transition plans (City of Cincinnati, ODOT), Ohio DNR pages | Not yet | not started | next batch |

Excluded on purpose: the Visit Hamilton County "accessible guide to parks" blog is about Hamilton County, Indiana.

