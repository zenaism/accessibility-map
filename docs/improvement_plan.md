# Improvement plan (review of 2026-11-18)

**Progress 2026-11-18: Phase 0 items 0.1 to 0.10 are built and tested (marked DONE below).** Still needs you for 0.8 and 0.9: re-run `supabase/problem_reports.sql`.

Three independent read-only reviews of the code, the map and form, the data pipeline and the docs, plus my own checks (secret scan, lint, dependencies). **Verified** = I reproduced it myself with a command; **reported** = a reviewer read it in the code and I have not re-run it yet. Nothing here has been fixed yet: this is the order I propose.

Clean results: no secrets in the 113 commits (gitleaks), only a publishable Supabase key is published, no SQL injection found in the report and rating functions, all `link_id` values in the map data match the database rules.

## Phase 0: before any more crawling or any public test of the form (safety and compliance)

| # | Problem | Status | Fix | Size |
|---|---|---|---|---|
| 0.1 DONE | **Redirects are never followed.** `handle_httpstatus_all` hands 3xx answers to the page parser, which ignores `Location`. An `http://` seed that redirects to `https://` dead-ends; a `/terms` probe that redirects is never read, so the terms check silently passes. Many Oxford seeds are `http://`. | reported (code read: no 3xx handling in `spider.py`) | follow the redirect: normalise the target, scope-check it, queue it, mark the original as redirected | M |
| 0.2 DONE | **Terms-restricted sites are restricted too late and not remembered.** Pages fetched before the terms page is read stay in the documents table and raw files; the restricted set is in memory only, so a resume or `--fresh` crawl forgets it; spec hosts like `www.x.com` never match because the crawler strips `www.`. | reported | store the restricted state in the frontier, filter `docs.build` and raw files by it, normalise spec hosts, fetch terms pages before the seed, do not request restricted seeds | M |
| 0.3 DONE | **Terms wording misses plain bans.** "Do not scrape this site." is not detected. | verified (returned none). The reviewer's false positives ("robotics club") did not reproduce | add `do not` and `don't`, add word boundaries, probe more terms paths (footer links, `/about/terms`) | S |
| 0.4 DONE | **Wrong answers on negated sentences**, the most serious data bug: "There is no step-free entrance" gives *yes*; "restroom is not accessible" gives *yes*; "Wheelchairs are not available to borrow" gives *yes*; "Dogs are not permitted, except service animals" gives *no*. | verified | look for negation across the whole sentence including the match; make `positive_no` apply only when the match itself is the "no"; drop "only" and "many" from the limited-words list; add a regression test for each sentence | M |
| 0.5 DONE | **Over-matching rules** give false yes: "Our website is fully accessible" counts as a step-free entrance; "ramp to the loading dock"; `restrooms` across a semicolon; kids' scooters; "drop off your donations"; "closed for lunch" as a notice; PDF line wraps lose the negation ("is\nnot accessible"). | reported | tighten each pattern, join wrapped lines before splitting sentences, tests from these sentences | M |
| 0.6 DONE | **Personal data still leaks:** the `phones` column keeps a cell number after scrubbing (verified); emails split across lines in PDFs survive; the role-address rule keeps `adam@` and `help.jsmith@`; "(cell)" after a number is missed; "Home | Contact (614)…" is wrongly removed. | phones leak verified; rest reported | scrub the `phones` and `hours` columns, collapse whitespace first, strict role allow-list, extract phones after scrubbing, tests with PDF-style text | M |
| 0.7 DONE | **Page relevance matches substrings:** "Canada … parade … tip" scores 1.0, so the adaptive stop, the drop-after-five-pages rule and the snippet reader barely work. | verified | match whole words only | S |
| 0.8 DONE | **Form can be flooded:** the rate limit uses a device id the browser chooses; a script with new ids can fill the free database (about 1,200 reports at 400 KB each); same for ratings; the check also races. | reported | global cap in the database function (for example 200 per hour), smaller photo limit (about 250 KB); later a CAPTCHA or edge function. **Needs you: re-run the SQL** | S |
| 0.9 DONE | **Retry of the 10th report is rejected** (rate check runs before the duplicate check), and "Delete" always says deleted even if nothing was deleted. | reported | return early when the report id already exists; check the delete result | S |
| 0.10 DONE | LLM failures are stored as model results (`rules+llm`, confidence 0.6) when Ollama is down; a half-written cache line stops extraction. | reported | keep `rules` and base confidence on error, skip bad cache lines | S |

## Phase 1: before the first data release

| # | Problem | Status | Fix | Size |
|---|---|---|---|---|
| 1.1 | **Licence handling is unsafe.** "CC BY-NC", "CC BY-ND" and "Not open to public use" all score as fully open; a liability disclaimer is stored as a licence; "Confirm redistribution terms" counts as a licence, so unconfirmed sources are never capped. | scoring verified | add `license_status: open / restricted / unconfirmed`, an allow-list of known licence ids, detect NC / ND, cap the tier for unconfirmed, never store disclaimers as licences | M |
| 1.2 | **"Never overwritten" is false for the data:** each fetch overwrites the observation file; old values are gone. Prediction needs history. | reported | dated append-only snapshots or a change log with `valid_to` | L |
| 1.3 | Fact-level confidence (freshness, corroboration) is described in the docs but never used; `confidence` is just the source score. | reported | wire `fact_confidence` into the schema upgrade, or fix the docs | M |
| 1.4 | **Failures are silent:** cards failures reported as "inventory" errors, exit code 0 when sources fail, dead catalogues look like "nothing found", "archived 0" shown when a region has no feed. | reported | exit codes, log catalogue errors, split the error handling | S |
| 1.5 | Stale outputs reused: documents and facts files are written only when non-empty, so an empty rerun leaves the old file; archive files are written non-atomically (a crash leaves a truncated file kept forever); a gzip sitemap has no size limit. | reported | clear stale files, write to a temp file and rename, cap decompression | S |
| 1.6 | **Release packaging missing:** no LICENSE, CITATION, changelog, licences manifest or versioned release; OSM share-alike (ODbL) not covered in the compliance doc; third-party PDFs and large generated pages are committed. | reported | add them, decide what stays in git | M |
| 1.7 | Dependencies: `rapidfuzz` (verified), `gtfs-realtime-bindings`, `scipy` and `duckdb` are imported but not declared in the right group. | rapidfuzz verified | declare them; add a base-install test | S |
| 1.8 | Counsel and library review of releasing derived data; role email address for the crawler page; retention rule confirmation. | open | **needs you** | |

## Phase 2: toward the nationwide goal

| # | Problem | Fix | Size |
|---|---|---|---|
| 2.1 | The metric coordinate system is fixed to UTM zone 16 (verified); DC and Baltimore are zone 18, so their measurements are slightly off | use the per-region zone the code already has | S |
| 2.2 | City names hard-coded in the map exporter and in the agreement check (DC only) | generate from config | M |
| 2.3 | Region size limited to a city; discovery drops state-wide layers, so state sources must be seeded by hand | allow state regions; relax the size filter; add Socrata and Data.gov at state level | L |
| 2.4 | No stable place id across sources, no unit column; matching by 15 m distance for DC only | canonical place ids, units column, cross-source entity matching | L |
| 2.5 | Rendered pages are less polite than plain fetches (browser sub-requests not throttled, can end on another site); `Crawl-delay` ignored; probes bypass the per-site budget; resume resets budgets; `drop_duplicates` in the matcher hides same-name branches | route through the same checks, honour `Crawl-delay`, count probes, persist counters | M |
| 2.6 | Candidate lifecycle: nothing marks ingested, stale or retired; a hand-written rejection; a `maryland` key not in the region list | automate the lifecycle | M |
| 2.7 | Trust weights are untuned guesses; track record and agreement are almost always empty | use the calibration set and agreement checks | L |

## Phase 3: map and form polish

| # | Problem | Status | Fix |
|---|---|---|---|
| 3.1 | **Grey button borders are too faint** (about 1.5 to 1:1 against white; the accessibility standard asks for 3:1) | reported, matches my own look at the screenshots | darker border (`#6b7280`) on card, popup and floating buttons |
| 3.2 | Floating button covers the open legend on tablets (width 720 to 890 px) | reported | hide it while the legend is open |
| 3.3 | A malformed link such as `#place=%` breaks map start-up | reported | catch the decoding error |
| 3.4 | CSV export can run spreadsheet formulas; deleted reports remain in old exports | reported | prefix risky cells; wipe the photos folder before each export |
| 3.5 | No integrity hashes or content security policy on the map libraries | reported | vendor or hash them, add a policy |
| 3.6 | Escape the server error text and two data-driven attributes; honeypot field can be autofilled and silently discards a real report; iOS bottom safe area; close button scrolls away; closing while sending creates duplicates; websites without `https://` become broken links (9 places); "Anonymous" wording while user agent and page address are stored | reported | small fixes |
| 3.7 | Errors not tied to their fields for screen readers; double announcement of the error summary | reported | `aria-describedby`, drop `role=alert` |

## Phase 4: docs and housekeeping

- Fix the dead link to `docs/research_plan.md` in the README (verified); update stale decision statuses (D-12, D-14, D-16, D-17, D-20, D-27 say "proposed" but are built; D-12 and D-16 contradict) and the "planned" rows in `system_overview.md`; the README says Baltimore collection is running, but it only has history archiving.
- Ignore Obsidian files, `finish_cleanup.sh`, personal notes and `data/ledger/` in `.gitignore`.
- Lint also `scripts/` (35 issues, mostly long lines); add a fast test tier (the full suite takes 14 minutes and the weekly refresh calls it).
- Cards embed today's date, so the trust score and tracked card files change daily; use the retrieval date only.

## Suggested order

1. **Phase 0** (about two working days): items 0.1 to 0.7 and 0.10 are code only. 0.8 and 0.9 need you to re-run the SQL.
2. **1.1, 1.4, 1.5, 1.7** (licence safety, loud failures, dependencies) next, since they gate any release.
3. **Phase 3** in one pass (small, visible).
4. **1.2 history and 1.6 release packaging**, then **Phase 2** for new states.

Not worth doing now: tuning trust weights (2.7) before there is more reference data; vendoring maps.
